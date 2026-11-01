"""Unit tests for DareFX EconomicNewsFilter."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from darefx.risk.news_filter import EconomicNewsFilter, EconomicEvent


class TestEconomicNewsFilter:
    """Test suite for high-impact news filter and calendar freeze."""

    def test_news_freeze_active_during_window(self):
        filter_svc = EconomicNewsFilter(buffer_minutes_before=30, buffer_minutes_after=30)

        event_time = datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc)
        mock_event = EconomicEvent(
            title="Non-Farm Employment Change",
            country="USD",
            date=event_time,
            impact="High",
        )
        filter_svc._cached_events = [mock_event]
        filter_svc._last_fetch_time = datetime.now(timezone.utc)

        # 1. 20 minutes before event -> FROZEN
        frozen, reason = filter_svc.is_news_freeze(
            symbol="EURUSD",
            check_time=datetime(2026, 11, 2, 13, 10, tzinfo=timezone.utc),
        )
        assert frozen is True
        assert "Non-Farm Employment Change" in reason

        # 2. 10 minutes after event -> FROZEN
        frozen, reason = filter_svc.is_news_freeze(
            symbol="EURUSD",
            check_time=datetime(2026, 11, 2, 13, 40, tzinfo=timezone.utc),
        )
        assert frozen is True

        # 3. 35 minutes before event -> NOT FROZEN
        frozen, _ = filter_svc.is_news_freeze(
            symbol="EURUSD",
            check_time=datetime(2026, 11, 2, 12, 55, tzinfo=timezone.utc),
        )
        assert frozen is False

        # 4. 35 minutes after event -> NOT FROZEN
        frozen, _ = filter_svc.is_news_freeze(
            symbol="EURUSD",
            check_time=datetime(2026, 11, 2, 14, 5, tzinfo=timezone.utc),
        )
        assert frozen is False

    def test_news_freeze_ignores_other_currencies(self):
        filter_svc = EconomicNewsFilter(buffer_minutes_before=30, buffer_minutes_after=30)
        event_time = datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc)
        mock_event = EconomicEvent(
            title="AUD Cash Rate",
            country="AUD",
            date=event_time,
            impact="High",
        )
        filter_svc._cached_events = [mock_event]
        filter_svc._last_fetch_time = datetime.now(timezone.utc)

        # EURUSD is unaffected by AUD event
        frozen, _ = filter_svc.is_news_freeze(
            symbol="EURUSD",
            check_time=datetime(2026, 11, 2, 13, 20, tzinfo=timezone.utc),
        )
        assert frozen is False

    def test_news_freeze_ignores_low_impact(self):
        filter_svc = EconomicNewsFilter(buffer_minutes_before=30, buffer_minutes_after=30)
        event_time = datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc)
        mock_event = EconomicEvent(
            title="Factory Orders",
            country="USD",
            date=event_time,
            impact="Low",
        )
        filter_svc._cached_events = [mock_event]
        filter_svc._last_fetch_time = datetime.now(timezone.utc)

        frozen, _ = filter_svc.is_news_freeze(
            symbol="EURUSD",
            check_time=datetime(2026, 11, 2, 13, 20, tzinfo=timezone.utc),
        )
        assert frozen is False

    def test_fetch_events_with_mock_api(self):
        filter_svc = EconomicNewsFilter()
        fake_api_data = [
            {
                "title": "US CPI m/m",
                "country": "USD",
                "date": "2026-11-04T08:30:00-04:00",
                "impact": "High",
                "forecast": "0.2%",
                "previous": "0.2%",
            }
        ]

        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fake_api_data
            mock_get.return_value = mock_resp

            events = filter_svc.fetch_events(force_refresh=True)
            assert len(events) == 1
            assert events[0].title == "US CPI m/m"
            assert events[0].country == "USD"
            assert events[0].impact == "High"
