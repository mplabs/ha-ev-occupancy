"""EV Occupancy integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML."""
    if DOMAIN not in config:
        return True

    _LOGGER.debug("Setting up %s from YAML", DOMAIN)
    return True
