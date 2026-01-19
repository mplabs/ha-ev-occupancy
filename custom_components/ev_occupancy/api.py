"""API client for EV Occupancy."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class EvOccupancyApiError(Exception):
    """Error communicating with the EV Occupancy API."""


class EvOccupancyApiClient:
    """Thin client for the Iternio charger API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        headers: dict[str, str] | None,
        timeout: int = 10,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def fetch_details(self, charger_ids: list[int]) -> Any:
        """Fetch charger details for multiple charger IDs."""
        payload = {"chargerIds": charger_ids}
        return await self._request(
            "POST",
            "/2/charger/_get/details",
            json=payload,
        )

    async def fetch_session_summary(self, charger_id: int) -> Any:
        """Fetch session summary for a single charger."""
        return await self._request(
            "GET",
            f"/2/charger/{charger_id}/charging-sessions/summary",
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        headers = kwargs.pop("headers", {})
        merged_headers = {**self._headers, **headers}

        try:
            async with self._session.request(
                method,
                url,
                headers=merged_headers,
                timeout=self._timeout,
                **kwargs,
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise EvOccupancyApiError(
                        f"HTTP {response.status} for {method} {path}: {body}"
                    )
                return await response.json(content_type=None)
        except aiohttp.ClientError as err:
            _LOGGER.debug("HTTP error for %s %s: %s", method, path, err)
            raise EvOccupancyApiError(str(err)) from err
