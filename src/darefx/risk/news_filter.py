"""High-Impact Economic News Filter for DareFX.

Protects live trading capital by pausing new trade executions during
high-impact macro releases (e.g. NFP, CPI, FOMC, ECB Rate Decisions)
where spreads widen drastically and severe slippage occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging
from typing import Any
import requests

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


@dataclass
class EconomicEvent:
    """Structure for an economic calendar event."""

    title: str
    country: str
    date: datetime
    impact: str
    forecast: str = ""
    previous: str = ""


class EconomicNewsFilter:
    """Monitors upcoming high-impact macroeconomic news and enforces trading freezes."""

    def __init__(
        self,
        calendar_url: str = CALENDAR_URL,
        buffer_minutes_before: int = 30,
        buffer_minutes_after: int = 30,
        cache_ttl_seconds: int = 3600,
        request_timeout: int = 5,
    ) -> None:
        self.calendar_url = calendar_url
        self.buffer_before = timedelta(minutes=buffer_minutes_before)
        self.buffer_after = timedelta(minutes=buffer_minutes_after)
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.request_timeout = request_timeout

        self._cached_events: list[EconomicEvent] = []
        self._last_fetch_time: datetime | None = None

    def fetch_events(self, force_refresh: bool = False) -> list[EconomicEvent]:
        """Fetch weekly calendar events with in-memory caching."""
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and self._last_fetch_time is not None
            and (now - self._last_fetch_time) < self.cache_ttl
        ):
            return self._cached_events

        try:
            resp = requests.get(self.calendar_url, timeout=self.request_timeout)
            if resp.status_code != 200:
                logger.warning(
                    "Failed to fetch economic calendar: HTTP %d. Using existing cache.",
                    resp.status_code,
                )
                return self._cached_events

            raw_events = resp.json()
            events: list[EconomicEvent] = []
            for item in raw_events:
                # Expected format: 2026-11-02T08:30:00-04:00 or ISO format
                date_str = item.get("date", "")
                if not date_str:
                    continue

                try:
                    event_dt = datetime.fromisoformat(date_str)
                    if event_dt.tzinfo is None:
                        event_dt = event_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

                events.append(
                    EconomicEvent(
                        title=item.get("title", "Unknown Event"),
                        country=str(item.get("country", "")).upper(),
                        date=event_dt,
                        impact=str(item.get("impact", "")).capitalize(),
                        forecast=item.get("forecast", ""),
                        previous=item.get("previous", ""),
                    )
                )

            self._cached_events = events
            self._last_fetch_time = now
            logger.info("Loaded %d economic calendar events successfully.", len(events))
            return self._cached_events
        except Exception as err:
            logger.warning("Error fetching economic calendar: %s. Proceeding with cache.", err)
            return self._cached_events

    def is_news_freeze(
        self,
        symbol: str = "EURUSD",
        check_time: datetime | None = None,
    ) -> tuple[bool, str]:
        """Check if trading for a given symbol is frozen due to high-impact news.

        Returns (is_frozen, reason_string).
        """
        now = check_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        events = self.fetch_events()

        # Determine relevant currencies for the currency pair
        curr_a = symbol[:3].upper()
        curr_b = symbol[3:6].upper() if len(symbol) >= 6 else ""
        relevant_currencies = {curr_a, curr_b}

        for ev in events:
            if ev.country not in relevant_currencies:
                continue

            if ev.impact not in ("High", "Red"):
                continue

            freeze_start = ev.date - self.buffer_before
            freeze_end = ev.date + self.buffer_after

            if freeze_start <= now <= freeze_end:
                # Format time in WIB for operator clarity
                wib_dt = ev.date.astimezone(timezone(timedelta(hours=7)))
                wib_str = wib_dt.strftime("%H:%M WIB (%d %b)")
                reason = (
                    f"Rilis Berita High-Impact [{ev.country}] '{ev.title}' pada {wib_str}. "
                    f"Jendela pengaman {int(self.buffer_before.total_seconds() / 60)} menit aktif."
                )
                logger.warning("News freeze active: %s", reason)
                return True, reason

        return False, ""

    def get_upcoming_events(
        self,
        symbol: str = "EURUSD",
        hours_ahead: int = 24,
    ) -> list[dict[str, Any]]:
        """Return high and medium impact events within the next N hours."""
        now = datetime.now(timezone.utc)
        events = self.fetch_events()

        curr_a = symbol[:3].upper()
        curr_b = symbol[3:6].upper() if len(symbol) >= 6 else ""
        relevant_currencies = {curr_a, curr_b}

        cutoff = now + timedelta(hours=hours_ahead)
        upcoming = []

        for ev in events:
            if ev.country not in relevant_currencies:
                continue
            if ev.impact not in ("High", "Red", "Medium"):
                continue

            if now <= ev.date <= cutoff:
                wib_dt = ev.date.astimezone(timezone(timedelta(hours=7)))
                upcoming.append(
                    {
                        "title": ev.title,
                        "country": ev.country,
                        "impact": ev.impact,
                        "time_wib": wib_dt.strftime("%H:%M WIB"),
                        "date_wib": wib_dt.strftime("%d %b %Y"),
                        "forecast": ev.forecast,
                        "previous": ev.previous,
                    }
                )

        return upcoming
