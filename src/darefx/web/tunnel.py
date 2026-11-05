"""Cloudflare Tunnel Manager for DareFX Web Cockpit.

Provides automated, zero-configuration HTTPS public domain exposure via Cloudflare
Tunnel (Quick Tunnels or Named Tunnels with custom domains).
Eliminates the need for manual port-forwarding, static public IPs, or firewall punching.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CLOUDFLARED_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
)


class CloudflareTunnel:
    """Manages cloudflared background lifecycle and public HTTPS domain discovery."""

    def __init__(
        self,
        local_port: int = 8888,
        token: str | None = None,
        custom_domain: str | None = None,
        storage_dir: Path | None = None,
    ) -> None:
        self.local_port = local_port
        self.token = token or os.getenv("CLOUDFLARE_TUNNEL_TOKEN")
        self.custom_domain = custom_domain or os.getenv("DAREFX_CUSTOM_DOMAIN")
        self.storage_dir = storage_dir or (Path.home() / ".darefx")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._proc: subprocess.Popen[str] | None = None
        self._url: str | None = None
        self._lock = threading.Lock()

    @property
    def url_file(self) -> Path:
        return self.storage_dir / "tunnel_url.txt"

    @property
    def public_url(self) -> str | None:
        if self._url:
            return self._url
        if self.url_file.exists():
            try:
                return self.url_file.read_text().strip()
            except OSError:
                pass
        return None

    def ensure_binary(self) -> Path:
        """Find existing cloudflared binary or auto-download to ~/.local/bin/cloudflared."""
        # 1. Check in PATH
        system_bin = shutil.which("cloudflared")
        if system_bin:
            return Path(system_bin)

        # 2. Check local user bin
        local_bin = Path.home() / ".local" / "bin" / "cloudflared"
        if local_bin.exists() and os.access(local_bin, os.X_OK):
            return local_bin

        # 3. Auto-download binary
        local_bin.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading cloudflared binary from %s...", CLOUDFLARED_DOWNLOAD_URL)
        subprocess.run(
            ["curl", "-fsSL", CLOUDFLARED_DOWNLOAD_URL, "-o", str(local_bin)],
            check=True,
            timeout=60,
        )
        local_bin.chmod(0o755)
        logger.info("cloudflared binary ready at %s", local_bin)
        return local_bin

    def start(self, timeout_sec: float = 20.0) -> str | None:
        """Start cloudflared in the background and capture public HTTPS domain."""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return self.public_url

            bin_path = self.ensure_binary()

            if self.token:
                logger.info("Starting Named Cloudflare Tunnel with provided token...")
                cmd = [
                    str(bin_path),
                    "tunnel",
                    "--no-autoupdate",
                    "run",
                    "--token",
                    self.token,
                ]
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                self._url = self.custom_domain or f"https://{self.custom_domain}"
                if self._url:
                    self.url_file.write_text(self._url)
                return self._url

            # Quick Tunnel mode
            logger.info("Starting Cloudflare Quick Tunnel for port %d...", self.local_port)
            cmd = [
                str(bin_path),
                "tunnel",
                "--url",
                f"http://127.0.0.1:{self.local_port}",
            ]
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )

            # Read stream until URL discovered or timeout
            discovered_url = None
            start_time = time.time()

            assert self._proc.stdout is not None
            while time.time() - start_time < timeout_sec:
                if self._proc.poll() is not None:
                    break
                line = self._proc.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    discovered_url = m.group(0)
                    break

            if discovered_url:
                self._url = discovered_url
                self.url_file.write_text(discovered_url)
                logger.info("Cloudflare Tunnel active at %s", discovered_url)
                return discovered_url

            logger.warning("Cloudflare Tunnel started but public URL extraction timed out.")
            return None

    def stop(self) -> None:
        """Stop background tunnel process cleanly."""
        with self._lock:
            if self._proc:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=2.0)
                except Exception:
                    with contextlib.suppress(Exception):
                        self._proc.kill()
                self._proc = None

            if self.url_file.exists():
                with contextlib.suppress(OSError):
                    self.url_file.unlink()
            self._url = None
            logger.info("Cloudflare Tunnel stopped.")

    def is_running(self) -> bool:
        """Check if tunnel subprocess is alive."""
        return self._proc is not None and self._proc.poll() is None
