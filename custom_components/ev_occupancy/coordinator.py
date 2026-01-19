"""Data coordinators for EV Occupancy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import random
from typing import Any

import asyncio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EvOccupancyApiClient, EvOccupancyApiError

_LOGGER = logging.getLogger(__name__)

AVAILABLE_STATUSES = {"AVAILABLE"}
OCCUPIED_STATUSES = {"OCCUPIED", "CHARGING"}

MAX_BACKOFF_MULTIPLIER = 8
DEFAULT_JITTER_SECONDS = 10
MAX_EVSE_STATUSES = 5


@dataclass
class DetailsData:
    """Parsed charger details data."""

    charger_id: str
    name: str | None
    address: str | None
    network_name: str | None
    lat: float | None
    lon: float | None
    has_dynamic_status: bool | None
    source: str | None
    total_evses: int | None
    available_evses: int | None
    occupied_evses: int | None
    unknown_evses: int | None
    last_status_update: datetime | None
    freshness_minutes: int | None
    data_stale: bool | None
    evse_statuses: list[dict[str, Any]]


@dataclass
class SummaryData:
    """Parsed session summary data."""

    charger_id: str
    sessions_today: int | None
    sessions_7d: int | None
    sessions_30d: int | None
    last_session_end: datetime | None
    peak_hour_7d: int | None
    peak_weekday_30d: int | None


class BaseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Shared coordinator logic with jitter and backoff."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        name: str,
        base_interval: timedelta,
        jitter_seconds: int = DEFAULT_JITTER_SECONDS,
    ) -> None:
        super().__init__(hass, _LOGGER, name=name, update_interval=base_interval)
        self._base_interval = base_interval
        self._jitter_seconds = jitter_seconds
        self._failure_count = 0

    async def _async_fetch_data(self) -> dict[int, Any]:
        raise NotImplementedError

    async def _async_update_with_backoff(self) -> dict[int, Any]:
        if self._jitter_seconds > 0:
            await asyncio.sleep(random.uniform(0, self._jitter_seconds))
        try:
            data = await self._async_fetch_data()
        except UpdateFailed:
            self._set_backoff(False)
            raise
        self._set_backoff(True)
        return data

    def _set_backoff(self, success: bool) -> None:
        if success:
            self._failure_count = 0
            self.update_interval = self._base_interval
            return

        self._failure_count = min(self._failure_count + 1, MAX_BACKOFF_MULTIPLIER)
        multiplier = 2**self._failure_count
        max_multiplier = MAX_BACKOFF_MULTIPLIER
        multiplier = min(multiplier, max_multiplier)
        self.update_interval = self._base_interval * multiplier


class DetailsCoordinator(BaseCoordinator):
    """Coordinator for charger details polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EvOccupancyApiClient,
        charger_ids: list[str],
        stale_threshold_minutes: int,
        update_interval: timedelta,
    ) -> None:
        super().__init__(hass, name="ev_occupancy_details", base_interval=update_interval)
        self._api = api
        self._charger_ids = charger_ids
        self._stale_threshold = timedelta(minutes=stale_threshold_minutes)

    async def _async_fetch_data(self) -> dict[str, DetailsData]:
        try:
            payload = await self._api.fetch_details(self._charger_ids)
        except EvOccupancyApiError as err:
            raise UpdateFailed(str(err)) from err

        results = _parse_details_payload(
            payload,
            self._charger_ids,
            self._stale_threshold,
        )

        if not results:
            raise UpdateFailed("No charger details returned")

        if self.data:
            results = {**self.data, **results}
        return results

    async def _async_update_data(self) -> dict[str, DetailsData]:  # type: ignore[override]
        return await self._async_update_with_backoff()


class SummaryCoordinator(BaseCoordinator):
    """Coordinator for session summary polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EvOccupancyApiClient,
        charger_ids: list[str],
        update_interval: timedelta,
    ) -> None:
        super().__init__(hass, name="ev_occupancy_summary", base_interval=update_interval)
        self._api = api
        self._charger_ids = charger_ids

    async def _async_fetch_data(self) -> dict[str, SummaryData]:
        successes: dict[str, SummaryData] = {}
        failures: list[str] = []

        async def _fetch_one(charger_id: str) -> tuple[str, SummaryData | None]:
            try:
                payload = await self._api.fetch_session_summary(charger_id)
            except EvOccupancyApiError as err:
                _LOGGER.warning(
                    "Failed to fetch session summary for charger %s: %s",
                    charger_id,
                    err,
                )
                return charger_id, None

            summary = _parse_summary_payload(payload, charger_id)
            return charger_id, summary

        results = await asyncio.gather(
            *(_fetch_one(charger_id) for charger_id in self._charger_ids)
        )

        for charger_id, summary in results:
            if summary is None:
                failures.append(charger_id)
                continue
            successes[charger_id] = summary

        if not successes:
            raise UpdateFailed("No session summaries returned")

        if self.data:
            successes = {**self.data, **successes}

        if failures:
            _LOGGER.warning(
                "Session summary missing for chargers: %s",
                ", ".join(str(charger_id) for charger_id in failures),
            )

        return successes

    async def _async_update_data(self) -> dict[str, SummaryData]:  # type: ignore[override]
        return await self._async_update_with_backoff()


def _parse_details_payload(
    payload: Any,
    charger_ids: list[str],
    stale_threshold: timedelta,
) -> dict[str, DetailsData]:
    now = dt_util.utcnow()
    chargers = _extract_chargers(payload)
    by_id: dict[str, dict[str, Any]] = {}

    for charger in chargers:
        charger_id = _coerce_id(charger.get("id") or charger.get("chargerId"))
        if charger_id is None:
            continue
        by_id[charger_id] = charger

    results: dict[str, DetailsData] = {}

    for charger_id in charger_ids:
        charger = by_id.get(charger_id)
        if not charger:
            _LOGGER.warning("Charger %s missing from details payload", charger_id)
            results[charger_id] = DetailsData(
                charger_id=charger_id,
                name=None,
                address=None,
                network_name=None,
                lat=None,
                lon=None,
                has_dynamic_status=None,
                source=None,
                total_evses=None,
                available_evses=None,
                occupied_evses=None,
                unknown_evses=None,
                last_status_update=None,
                freshness_minutes=None,
                data_stale=True,
                evse_statuses=[],
            )
            continue

        evses = _extract_evses(charger)
        if evses is None:
            _LOGGER.warning("Charger %s missing EVSE data", charger_id)
            results[charger_id] = DetailsData(
                charger_id=charger_id,
                name=_get_str(charger, "name", "chargerName"),
                address=_get_str(charger, "address"),
                network_name=_get_str(charger, "networkName", "network"),
                lat=_get_lat(charger),
                lon=_get_lon(charger),
                has_dynamic_status=_get_bool(charger, "hasDynamicStatus"),
                source=_get_str(charger, "source"),
                total_evses=None,
                available_evses=None,
                occupied_evses=None,
                unknown_evses=None,
                last_status_update=None,
                freshness_minutes=None,
                data_stale=True,
                evse_statuses=[],
            )
            continue

        available = 0
        occupied = 0
        unknown = 0
        last_update: datetime | None = None
        evse_statuses: list[dict[str, Any]] = []

        for evse in evses:
            status = str(evse.get("status", "")).upper()
            last_updated = _parse_datetime(evse.get("statusLastUpdated"))

            if last_updated:
                if last_update is None or last_updated > last_update:
                    last_update = last_updated

            stale = _is_stale(last_updated, now, stale_threshold)
            if stale:
                unknown += 1
            elif status in AVAILABLE_STATUSES:
                available += 1
            elif status in OCCUPIED_STATUSES:
                occupied += 1
            else:
                unknown += 1

            if len(evse_statuses) < MAX_EVSE_STATUSES:
                evse_statuses.append(
                    {
                        "id": evse.get("id"),
                        "status": status or None,
                        "last_updated": dt_util.as_local(last_updated).isoformat()
                        if last_updated
                        else None,
                        "stale": stale,
                    }
                )

        total = len(evses)
        freshness_minutes = (
            int((now - last_update).total_seconds() / 60) if last_update else None
        )
        data_stale = _is_stale(last_update, now, stale_threshold)

        results[charger_id] = DetailsData(
            charger_id=charger_id,
            name=_get_str(charger, "name", "chargerName"),
            address=_get_str(charger, "address"),
            network_name=_get_str(charger, "networkName", "network"),
            lat=_get_lat(charger),
            lon=_get_lon(charger),
            has_dynamic_status=_get_bool(charger, "hasDynamicStatus"),
            source=_get_str(charger, "source"),
            total_evses=total,
            available_evses=available,
            occupied_evses=occupied,
            unknown_evses=unknown,
            last_status_update=last_update,
            freshness_minutes=freshness_minutes,
            data_stale=data_stale,
            evse_statuses=evse_statuses,
        )

    return results


def _parse_summary_payload(payload: Any, charger_id: str) -> SummaryData | None:
    telemetry = payload.get("chargerTelemetry") if isinstance(payload, dict) else None
    if not isinstance(telemetry, dict):
        _LOGGER.warning("Summary payload missing chargerTelemetry for %s", charger_id)
        return SummaryData(
            charger_id=charger_id,
            sessions_today=None,
            sessions_7d=None,
            sessions_30d=None,
            last_session_end=None,
            peak_hour_7d=None,
            peak_weekday_30d=None,
        )

    successful = telemetry.get("successful", [])
    if not isinstance(successful, list):
        _LOGGER.warning("Summary payload has unexpected successful list for %s", charger_id)
        return SummaryData(
            charger_id=charger_id,
            sessions_today=None,
            sessions_7d=None,
            sessions_30d=None,
            last_session_end=None,
            peak_hour_7d=None,
            peak_weekday_30d=None,
        )

    end_times: list[datetime] = []
    for entry in successful:
        if not isinstance(entry, dict):
            continue
        end_time = _parse_datetime(entry.get("endTime") or entry.get("end_time"))
        if end_time:
            end_times.append(end_time)

    now = dt_util.now()
    start_7d = now - timedelta(days=7)
    start_30d = now - timedelta(days=30)

    sessions_today = 0
    sessions_7d = 0
    sessions_30d = 0

    for end_time in end_times:
        local_end = dt_util.as_local(end_time)
        if local_end.date() == now.date():
            sessions_today += 1
        if end_time >= start_7d:
            sessions_7d += 1
        if end_time >= start_30d:
            sessions_30d += 1

    last_session_end = max(end_times) if end_times else None

    peak_hour_7d = _peak_hour(end_times, start_7d)
    peak_weekday_30d = _peak_weekday(end_times, start_30d)

    return SummaryData(
        charger_id=charger_id,
        sessions_today=sessions_today,
        sessions_7d=sessions_7d,
        sessions_30d=sessions_30d,
        last_session_end=last_session_end,
        peak_hour_7d=peak_hour_7d,
        peak_weekday_30d=peak_weekday_30d,
    )


def _extract_chargers(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("chargers", "chargerDetails", "chargerDetail", "data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    charger = payload.get("charger")
    if isinstance(charger, dict):
        return [charger]
    return []


def _extract_evses(charger: dict[str, Any]) -> list[dict[str, Any]] | None:
    for key in ("evses", "evse", "connectors"):
        value = charger.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1_000_000_000_000 else value
        return dt_util.utc_from_timestamp(seconds)
    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            return dt_util.assume_utc(parsed)
        return parsed
    return None


def _is_stale(
    last_updated: datetime | None,
    now: datetime,
    threshold: timedelta,
) -> bool:
    if last_updated is None:
        return True
    return now - last_updated > threshold


def _get_str(charger: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = charger.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _get_bool(charger: dict[str, Any], key: str) -> bool | None:
    value = charger.get(key)
    if isinstance(value, bool):
        return value
    return None


def _get_lat(charger: dict[str, Any]) -> float | None:
    for key in ("lat", "latitude"):
        value = charger.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    position = charger.get("position")
    if isinstance(position, dict):
        for key in ("lat", "latitude"):
            value = position.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _get_lon(charger: dict[str, Any]) -> float | None:
    for key in ("lon", "lng", "longitude"):
        value = charger.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    position = charger.get("position")
    if isinstance(position, dict):
        for key in ("lon", "lng", "longitude"):
            value = position.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _coerce_id(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return str(int(value))
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value
    return None


def _peak_hour(
    end_times: list[datetime],
    start: datetime,
) -> int | None:
    counts: dict[int, int] = {}
    for end_time in end_times:
        if end_time < start:
            continue
        hour = dt_util.as_local(end_time).hour
        counts[hour] = counts.get(hour, 0) + 1
    if not counts:
        return None
    return max(sorted(counts), key=lambda hour: counts[hour])


def _peak_weekday(
    end_times: list[datetime],
    start: datetime,
) -> int | None:
    counts: dict[int, int] = {}
    for end_time in end_times:
        if end_time < start:
            continue
        weekday = dt_util.as_local(end_time).weekday()
        counts[weekday] = counts.get(weekday, 0) + 1
    if not counts:
        return None
    return max(sorted(counts), key=lambda day: counts[day])
