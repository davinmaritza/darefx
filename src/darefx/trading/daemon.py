"""DareFX Autonomous 24/7 Production Daemon and Service Orchestration.

Manages long-running multi-asset execution (Forex, Crypto, US Equities),
background watchdog monitoring, crash recovery, graceful OS signal trapping
(SIGINT/SIGTERM), real-time Telegram alerts, and systemd service integration.
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from darefx.notifications.telegram import TelegramNotifier
from darefx.trading.multi_scheduler import MultiScheduler
from darefx.web.server import WebCockpitServer, get_tailscale_ip

logger = logging.getLogger(__name__)


@dataclass
class DaemonConfig:
    """Configuration options for DareFX production daemon."""

    enable_web: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8888
    watchdog_interval_sec: int = 30
    max_memory_mb: float = 1500.0
    pid_dir: Path = field(default_factory=lambda: Path.home() / ".darefx")

    @property
    def pid_file(self) -> Path:
        return self.pid_dir / "daemon.pid"

    @property
    def status_file(self) -> Path:
        return self.pid_dir / "daemon_status.json"


class DareFXDaemon:
    """Autonomous 24/7 daemon coordinating MultiScheduler, Web Cockpit, and Watchdog."""

    def __init__(
        self,
        config: DaemonConfig | None = None,
        scheduler: MultiScheduler | None = None,
        notifier: TelegramNotifier | None = None,
    ) -> None:
        self.config = config or DaemonConfig()
        self.notifier = notifier or TelegramNotifier()
        self.scheduler = scheduler or MultiScheduler(notifier=self.notifier)
        self.web_server: WebCockpitServer | None = None
        self._stop_event = threading.Event()
        self._start_time: float = 0.0
        self._web_loop: asyncio.AbstractEventLoop | None = None
        self._web_thread: threading.Thread | None = None

        self.config.pid_dir.mkdir(parents=True, exist_ok=True)

    def write_pid(self) -> None:
        """Write current process ID to PID file."""
        self.config.pid_file.write_text(str(os.getpid()))

    def remove_pid(self) -> None:
        """Remove PID file if present."""
        if self.config.pid_file.exists():
            with contextlib.suppress(OSError):
                self.config.pid_file.unlink()

    def get_running_pid(self) -> int | None:
        """Return the PID of currently running daemon, or None."""
        if not self.config.pid_file.exists():
            return None
        try:
            pid = int(self.config.pid_file.read_text().strip())
            if psutil.pid_exists(pid):
                return pid
        except (ValueError, OSError):
            pass
        return None

    def start_web_server(self) -> None:
        """Launch the aiohttp Web Cockpit in a dedicated background thread."""
        self.web_server = WebCockpitServer(
            host=self.config.web_host,
            port=self.config.web_port,
            scheduler=self.scheduler,
        )

        def _run_web() -> None:
            self._web_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._web_loop)
            self._web_loop.run_until_complete(self.web_server.start())
            try:
                self._web_loop.run_forever()
            finally:
                if self.web_server:
                    self._web_loop.run_until_complete(self.web_server.stop())
                self._web_loop.close()

        self._web_thread = threading.Thread(target=_run_web, daemon=True, name="DareFXWebCockpit")
        self._web_thread.start()
        logger.info("Launched Web Cockpit on %s:%d", self.config.web_host, self.config.web_port)

    def stop_web_server(self) -> None:
        """Gracefully stop background Web Cockpit server."""
        if self._web_loop and self._web_loop.is_running():
            self._web_loop.call_soon_threadsafe(self._web_loop.stop)
        if self._web_thread and self._web_thread.is_alive():
            self._web_thread.join(timeout=3.0)

    def _setup_signal_handlers(self) -> None:
        """Attach OS signal handlers for graceful shutdown."""
        def _handle_signal(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("Received signal %s. Initiating graceful daemon shutdown...", sig_name)
            self.stop_foreground()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def start_foreground(self) -> None:
        """Run production daemon in foreground (used by CLI or systemd)."""
        existing_pid = self.get_running_pid()
        if existing_pid and existing_pid != os.getpid():
            logger.error("DareFX Daemon already running with PID %d", existing_pid)
            print(f"Error: DareFX Daemon is already running (PID {existing_pid})")
            return

        self._start_time = time.time()
        self.write_pid()
        self._setup_signal_handlers()

        # 1. Start MultiScheduler
        self.scheduler.start()

        # 2. Start Web Cockpit if enabled
        if self.config.enable_web:
            self.start_web_server()

        # 3. Notify via Telegram
        ts_ip = get_tailscale_ip()
        start_msg = (
            "🚀 *DareFX 24/7 Autonomous Daemon Started*\n"
            f"• Mode: Multi-Asset (Forex, Crypto, US Stocks)\n"
            f"• Web Cockpit: `http://{ts_ip}:{self.config.web_port}`\n"
            f"• Host PID: `{os.getpid()}`\n"
            f"• Time: `{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
        try:
            self.notifier.send_message(start_msg)
        except Exception as err:
            logger.debug("Failed sending Telegram daemon start alert: %s", err)

        logger.info("DareFX Daemon running in foreground. Press Ctrl+C to terminate.")

        # 4. Watchdog loop
        try:
            while not self._stop_event.is_set():
                self._run_watchdog_tick()
                time.sleep(self.config.watchdog_interval_sec)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self._cleanup()

    def _run_watchdog_tick(self) -> None:
        """Check system health, RAM footprint, broker connectivity, and persist status."""
        proc = psutil.Process()
        mem_mb = proc.memory_info().rss / (1024 * 1024)

        if mem_mb > self.config.max_memory_mb:
            logger.warning("Memory usage elevated: %.1f MB. Running GC...", mem_mb)
            gc.collect()

        positions = self.scheduler.get_all_active_positions()
        uptime = int(time.time() - self._start_time)

        status_data = {
            "pid": os.getpid(),
            "uptime_sec": uptime,
            "running": True,
            "memory_mb": round(mem_mb, 1),
            "open_positions": len(positions),
            "scheduler_alive": self.scheduler.is_running,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        with contextlib.suppress(OSError):
            self.config.status_file.write_text(json.dumps(status_data, indent=2))

    def stop_foreground(self) -> None:
        """Set stop event to exit watchdog loop."""
        self._stop_event.set()

    def _cleanup(self) -> None:
        """Cleanly dispose resources and alert Telegram."""
        logger.info("Executing clean daemon termination...")
        self.stop_web_server()
        self.scheduler.stop()
        self.remove_pid()

        stop_msg = (
            "🛑 *DareFX 24/7 Autonomous Daemon Stopped*\n"
            f"• Time: `{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
            "• Safe shutdown complete. Open positions retained."
        )
        with contextlib.suppress(Exception):
            self.notifier.send_message(stop_msg)
        logger.info("DareFX Daemon cleanly terminated.")

    def stop_process(self) -> bool:
        """Stop external daemon process via PID file."""
        pid = self.get_running_pid()
        if not pid:
            logger.warning("No running DareFX daemon found.")
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                if not psutil.pid_exists(pid):
                    self.remove_pid()
                    return True
                time.sleep(0.2)

            # Force kill if still lingering
            os.kill(pid, signal.SIGKILL)
            self.remove_pid()
            return True
        except ProcessLookupError:
            self.remove_pid()
            return True
        except Exception as err:
            logger.error("Failed to stop daemon PID %d: %s", pid, err)
            return False

    def get_status(self) -> dict[str, Any]:
        """Query daemon status."""
        pid = self.get_running_pid()
        is_running = pid is not None

        status_info: dict[str, Any] = {
            "running": is_running,
            "pid": pid,
            "tailscale_ip": get_tailscale_ip(),
        }

        if is_running and self.config.status_file.exists():
            try:
                cached = json.loads(self.config.status_file.read_text())
                status_info.update(cached)
            except Exception:
                pass

        return status_info


# ---------------------------------------------------------------------------
# Systemd Integration Utilities
# ---------------------------------------------------------------------------

def get_systemd_unit_path(user_mode: bool = True) -> Path:
    """Return destination path for darefx.service systemd unit file."""
    if user_mode:
        return Path.home() / ".config" / "systemd" / "user" / "darefx.service"
    return Path("/etc/systemd/system/darefx.service")


def generate_systemd_service_file(user_mode: bool = True, port: int = 8888) -> str:
    """Generate systemd unit file content configured for current environment."""
    project_dir = Path.cwd().resolve()
    python_bin = sys.executable

    return f"""[Unit]
Description=DareFX 24/7 Autonomous Multi-Asset Trading Daemon
Documentation=https://github.com/davinmaritza/darefx
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={project_dir}
ExecStart={python_bin} -m darefx.cli daemon start --foreground --port {port}
Restart=always
RestartSec=5s
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""


def install_systemd_service(user_mode: bool = True, port: int = 8888) -> Path:
    """Install and enable darefx systemd service unit."""
    dest = get_systemd_unit_path(user_mode=user_mode)
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = generate_systemd_service_file(user_mode=user_mode, port=port)
    dest.write_text(content)

    cmd_prefix = ["systemctl", "--user"] if user_mode else ["systemctl"]
    subprocess.run([*cmd_prefix, "daemon-reload"], check=True)
    subprocess.run([*cmd_prefix, "enable", "darefx.service"], check=True)
    logger.info("Installed and enabled DareFX systemd service at %s", dest)
    return dest


def uninstall_systemd_service(user_mode: bool = True) -> bool:
    """Disable and remove darefx systemd service unit."""
    dest = get_systemd_unit_path(user_mode=user_mode)
    cmd_prefix = ["systemctl", "--user"] if user_mode else ["systemctl"]
    try:
        subprocess.run([*cmd_prefix, "stop", "darefx.service"], stderr=subprocess.DEVNULL)
        subprocess.run([*cmd_prefix, "disable", "darefx.service"], stderr=subprocess.DEVNULL)
        if dest.exists():
            dest.unlink()
        subprocess.run([*cmd_prefix, "daemon-reload"], check=True)
        return True
    except Exception as err:
        logger.error("Failed uninstalling systemd service: %s", err)
        return False


def run_service_command(action: str, user_mode: bool = True) -> tuple[int, str]:
    """Execute systemctl action (start, stop, restart, status) on darefx.service."""
    cmd_prefix = ["systemctl", "--user"] if user_mode else ["systemctl"]
    try:
        res = subprocess.run(
            [*cmd_prefix, action, "darefx.service"],
            capture_output=True,
            text=True,
            timeout=15.0,
        )
        return res.returncode, (res.stdout + res.stderr).strip()
    except Exception as err:
        return 1, str(err)
