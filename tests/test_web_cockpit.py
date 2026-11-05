"""Tests for DareFX Mobile Web Cockpit Server."""

import asyncio
from unittest.mock import MagicMock

from darefx.web.server import WebCockpitServer, get_tailscale_ip


def test_tailscale_ip_detection():
    ip = get_tailscale_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0


def test_web_cockpit_routes():
    async def _async_test():
        mock_scheduler = MagicMock()
        mock_scheduler.is_running = True
        mock_scheduler.config.execute_orders = False
        mock_scheduler.get_all_active_positions.return_value = []
        mock_scheduler.mt5_bridge.get_account_info.return_value = None
        mock_scheduler.panic_close_all.return_value = {
            "success": True,
            "total_closed": 0,
            "closed_tickets": [],
            "errors": [],
            "timestamp": "2026-11-06T00:00:00Z",
        }

        server = WebCockpitServer(host="127.0.0.1", port=8899, scheduler=mock_scheduler)

        # Test health endpoint
        req = MagicMock()
        health_resp = await server.handle_health(req)
        assert health_resp.status == 200
        assert "darefx-cockpit" in health_resp.text

        # Test status endpoint
        status_resp = await server.handle_status(req)
        assert status_resp.status == 200
        assert "account" in status_resp.text
        assert "equity" in status_resp.text

        # Test positions endpoint
        pos_resp = await server.handle_positions(req)
        assert pos_resp.status == 200
        assert "positions" in pos_resp.text

        # Test watchlist endpoint
        wl_resp = await server.handle_market_overview(req)
        assert wl_resp.status == 200
        assert "BTC/USDT" in wl_resp.text

        # Test panic close endpoint
        panic_resp = await server.handle_panic_close(req)
        assert panic_resp.status == 200
        assert "total_closed" in panic_resp.text
        mock_scheduler.panic_close_all.assert_called_once()

        # Test index HTML endpoint
        index_resp = await server.handle_index(req)
        assert index_resp.status == 200
        assert "DareFX Cockpit" in index_resp.text
        assert "PANIC CLOSE ALL" in index_resp.text

    asyncio.run(_async_test())
