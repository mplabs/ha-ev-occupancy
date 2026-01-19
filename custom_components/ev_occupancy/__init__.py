"""EV Occupancy integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform

from .api import EvOccupancyApiClient
from .const import (
    CONF_API_BASE_URL,
    CONF_CHARGER_IDS,
    CONF_HEADERS,
    CONF_SCAN_INTERVAL_DETAILS,
    CONF_SCAN_INTERVAL_SUMMARY,
    CONF_STALE_THRESHOLD_MINUTES,
    DEFAULT_API_BASE_URL,
    DEFAULT_SCAN_INTERVAL_DETAILS,
    DEFAULT_SCAN_INTERVAL_SUMMARY,
    DEFAULT_STALE_THRESHOLD_MINUTES,
    DOMAIN,
)
from .coordinator import DetailsCoordinator, SummaryCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CHARGER_IDS): vol.All(
                    cv.ensure_list, [vol.Coerce(int)], vol.Length(min=1)
                ),
                vol.Optional(CONF_API_BASE_URL, default=DEFAULT_API_BASE_URL): cv.url,
                vol.Optional(CONF_HEADERS, default={}): vol.Schema(
                    {cv.string: cv.string}, extra=vol.ALLOW_EXTRA
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL_DETAILS, default=DEFAULT_SCAN_INTERVAL_DETAILS
                ): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL_SUMMARY, default=DEFAULT_SCAN_INTERVAL_SUMMARY
                ): cv.positive_int,
                vol.Optional(
                    CONF_STALE_THRESHOLD_MINUTES,
                    default=DEFAULT_STALE_THRESHOLD_MINUTES,
                ): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    charger_ids = conf[CONF_CHARGER_IDS]
    api_base_url = conf[CONF_API_BASE_URL]
    headers = conf[CONF_HEADERS]

    session = async_get_clientsession(hass)
    api = EvOccupancyApiClient(session, api_base_url, headers)

    details_coordinator = DetailsCoordinator(
        hass,
        api,
        charger_ids,
        conf[CONF_STALE_THRESHOLD_MINUTES],
        timedelta(seconds=conf[CONF_SCAN_INTERVAL_DETAILS]),
    )
    summary_coordinator = SummaryCoordinator(
        hass,
        api,
        charger_ids,
        timedelta(seconds=conf[CONF_SCAN_INTERVAL_SUMMARY]),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].update(
        {
            "config": conf,
            "charger_ids": charger_ids,
            "details_coordinator": details_coordinator,
            "summary_coordinator": summary_coordinator,
        }
    )

    await details_coordinator.async_refresh()
    await summary_coordinator.async_refresh()

    for platform in PLATFORMS:
        await async_load_platform(hass, platform, DOMAIN, {}, config)

    _LOGGER.debug("Set up %s with %s chargers", DOMAIN, len(charger_ids))
    return True
