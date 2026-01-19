"""EV Occupancy integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
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
    data = await _async_build_runtime(hass, conf)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["yaml"] = data

    for platform in PLATFORMS:
        await async_load_platform(hass, platform, DOMAIN, {}, config)

    _LOGGER.debug("Set up %s from YAML with %s chargers", DOMAIN, len(data["charger_ids"]))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EV Occupancy from a config entry."""
    conf = _merge_entry_config(entry)
    data = await _async_build_runtime(hass, conf)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "Set up %s entry %s with %s chargers",
        DOMAIN,
        entry.entry_id,
        len(data["charger_ids"]),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_build_runtime(hass: HomeAssistant, conf: dict) -> dict:
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

    await details_coordinator.async_refresh()
    await summary_coordinator.async_refresh()

    return {
        "config": conf,
        "charger_ids": charger_ids,
        "details_coordinator": details_coordinator,
        "summary_coordinator": summary_coordinator,
    }


def _merge_entry_config(entry: ConfigEntry) -> dict:
    merged = {**entry.data, **entry.options}
    return {
        CONF_CHARGER_IDS: merged.get(CONF_CHARGER_IDS, []),
        CONF_API_BASE_URL: merged.get(CONF_API_BASE_URL, DEFAULT_API_BASE_URL),
        CONF_HEADERS: merged.get(CONF_HEADERS, {}),
        CONF_SCAN_INTERVAL_DETAILS: merged.get(
            CONF_SCAN_INTERVAL_DETAILS, DEFAULT_SCAN_INTERVAL_DETAILS
        ),
        CONF_SCAN_INTERVAL_SUMMARY: merged.get(
            CONF_SCAN_INTERVAL_SUMMARY, DEFAULT_SCAN_INTERVAL_SUMMARY
        ),
        CONF_STALE_THRESHOLD_MINUTES: merged.get(
            CONF_STALE_THRESHOLD_MINUTES, DEFAULT_STALE_THRESHOLD_MINUTES
        ),
    }
