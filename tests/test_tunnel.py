"""Tests for CloudflareTunnel manager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from darefx.web.tunnel import CloudflareTunnel


def test_tunnel_initialization(tmp_path: Path):
    tunnel = CloudflareTunnel(local_port=9999, storage_dir=tmp_path)
    assert tunnel.local_port == 9999
    assert tunnel.public_url is None
    assert tunnel.is_running() is False


def test_tunnel_url_file_reading(tmp_path: Path):
    tunnel = CloudflareTunnel(local_port=9999, storage_dir=tmp_path)
    test_url = "https://alpha-beta-gamma.trycloudflare.com"
    tunnel.url_file.write_text(test_url)

    assert tunnel.public_url == test_url


@patch("shutil.which")
def test_ensure_binary_finds_path(mock_which):
    mock_which.return_value = "/usr/bin/cloudflared"
    tunnel = CloudflareTunnel(local_port=9999)
    bin_path = tunnel.ensure_binary()
    assert str(bin_path) == "/usr/bin/cloudflared"


def test_tunnel_stop_lifecycle(tmp_path: Path):
    tunnel = CloudflareTunnel(local_port=9999, storage_dir=tmp_path)
    tunnel.url_file.write_text("https://sample.trycloudflare.com")

    mock_proc = MagicMock()
    tunnel._proc = mock_proc
    tunnel._url = "https://sample.trycloudflare.com"

    tunnel.stop()
    mock_proc.terminate.assert_called_once()
    assert tunnel.public_url is None
    assert not tunnel.url_file.exists()
