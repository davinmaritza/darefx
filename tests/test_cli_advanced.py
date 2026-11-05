"""Tests for advanced DareFX CLI commands (web, daemon, service)."""

from typer.testing import CliRunner

from darefx.cli import app

runner = CliRunner()


def test_cli_web_help():
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    assert "Launch DareFX Mobile Web Cockpit" in result.output
    assert "--port" in result.output


def test_cli_daemon_help():
    result = runner.invoke(app, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output
    assert "status" in result.output


def test_cli_daemon_status():
    result = runner.invoke(app, ["daemon", "status"])
    assert result.exit_code == 0
    assert "DareFX 24/7 Daemon Status" in result.output


def test_cli_service_help():
    result = runner.invoke(app, ["service", "--help"])
    assert result.exit_code == 0
    assert "install" in result.output
    assert "uninstall" in result.output
    assert "status" in result.output
