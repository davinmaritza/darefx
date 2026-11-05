"""Tests for DareFX 24/7 Production Daemon and Service Orchestration."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from darefx.trading.daemon import (
    DaemonConfig,
    DareFXDaemon,
    generate_systemd_service_file,
    get_systemd_unit_path,
)


def test_daemon_pid_lifecycle(tmp_path: Path):
    cfg = DaemonConfig(pid_dir=tmp_path)
    daemon = DareFXDaemon(config=cfg)

    assert daemon.get_running_pid() is None

    daemon.write_pid()
    assert cfg.pid_file.exists()
    assert daemon.get_running_pid() is not None

    daemon.remove_pid()
    assert not cfg.pid_file.exists()
    assert daemon.get_running_pid() is None


def test_daemon_watchdog_tick(tmp_path: Path):
    mock_scheduler = MagicMock()
    mock_scheduler.is_running = True
    mock_scheduler.get_all_active_positions.return_value = []

    cfg = DaemonConfig(pid_dir=tmp_path)
    daemon = DareFXDaemon(config=cfg, scheduler=mock_scheduler)
    daemon._start_time = 1000.0

    daemon._run_watchdog_tick()
    assert cfg.status_file.exists()

    data = json.loads(cfg.status_file.read_text())
    assert data["running"] is True
    assert "memory_mb" in data
    assert "open_positions" in data
    assert data["open_positions"] == 0


def test_daemon_status_reporting(tmp_path: Path):
    cfg = DaemonConfig(pid_dir=tmp_path)
    daemon = DareFXDaemon(config=cfg)

    status_stopped = daemon.get_status()
    assert status_stopped["running"] is False

    daemon.write_pid()
    status_running = daemon.get_status()
    assert status_running["running"] is True
    assert status_running["pid"] is not None

    daemon.remove_pid()


def test_systemd_service_generation():
    unit_text = generate_systemd_service_file(user_mode=True, port=8888)
    assert "[Unit]" in unit_text
    assert "DareFX 24/7 Autonomous Multi-Asset Trading Daemon" in unit_text
    assert "ExecStart=" in unit_text
    assert "--port 8888" in unit_text
    assert "Restart=always" in unit_text

    unit_path = get_systemd_unit_path(user_mode=True)
    assert "darefx.service" in str(unit_path)
