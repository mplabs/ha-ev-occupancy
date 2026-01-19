"""Config flow for EV Occupancy."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import (
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_CHARGER_IDS,
    CONF_HEADERS,
    CONF_HEADERS_JSON,
    CONF_SCAN_INTERVAL_DETAILS,
    CONF_SCAN_INTERVAL_SUMMARY,
    CONF_STALE_THRESHOLD_MINUTES,
    DEFAULT_API_BASE_URL,
    DEFAULT_SCAN_INTERVAL_DETAILS,
    DEFAULT_SCAN_INTERVAL_SUMMARY,
    DEFAULT_STALE_THRESHOLD_MINUTES,
    DOMAIN,
)


class EvOccupancyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EV Occupancy."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _validate_user_input(user_input)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="EV Occupancy", data=data)

        defaults = _defaults_from_input(user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(defaults),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return EvOccupancyOptionsFlow(config_entry)


class EvOccupancyOptionsFlow(config_entries.OptionsFlow):
    """Handle options for EV Occupancy."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle the options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _validate_user_input(user_input)
            if not errors:
                return self.async_create_entry(title="", data=data)

        defaults = _defaults_from_entry(self._entry, user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_CHARGER_IDS, default=defaults[CONF_CHARGER_IDS]): str,
            vol.Optional(
                CONF_API_BASE_URL,
                default=defaults[CONF_API_BASE_URL],
            ): str,
            vol.Optional(CONF_API_KEY, default=defaults[CONF_API_KEY]): TextSelector(
                TextSelectorConfig(type="password")
            ),
            vol.Optional(
                CONF_HEADERS_JSON,
                default=defaults[CONF_HEADERS_JSON],
            ): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_SCAN_INTERVAL_DETAILS,
                default=defaults[CONF_SCAN_INTERVAL_DETAILS],
            ): int,
            vol.Optional(
                CONF_SCAN_INTERVAL_SUMMARY,
                default=defaults[CONF_SCAN_INTERVAL_SUMMARY],
            ): int,
            vol.Optional(
                CONF_STALE_THRESHOLD_MINUTES,
                default=defaults[CONF_STALE_THRESHOLD_MINUTES],
            ): int,
        }
    )


def _validate_user_input(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}

    charger_ids_raw = str(user_input.get(CONF_CHARGER_IDS, "")).strip()
    charger_ids: list[int] = []
    for token in charger_ids_raw.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit():
            errors[CONF_CHARGER_IDS] = "invalid_charger_ids"
            break
        charger_ids.append(int(token))

    if not charger_ids and CONF_CHARGER_IDS not in errors:
        errors[CONF_CHARGER_IDS] = "invalid_charger_ids"

    headers_json = str(user_input.get(CONF_HEADERS_JSON, "")).strip()
    headers: dict[str, str] = {}
    if headers_json:
        try:
            parsed = json.loads(headers_json)
        except json.JSONDecodeError:
            errors[CONF_HEADERS_JSON] = "invalid_headers"
        else:
            if not isinstance(parsed, dict):
                errors[CONF_HEADERS_JSON] = "invalid_headers"
            else:
                for key, value in parsed.items():
                    headers[str(key)] = str(value)

    api_key = str(user_input.get(CONF_API_KEY, "")).strip()
    if api_key and "x-api-key" not in headers:
        headers["x-api-key"] = api_key

    data = {
        CONF_CHARGER_IDS: charger_ids,
        CONF_API_BASE_URL: str(
            user_input.get(CONF_API_BASE_URL, DEFAULT_API_BASE_URL)
        ).strip(),
        CONF_HEADERS: headers,
        CONF_SCAN_INTERVAL_DETAILS: int(
            user_input.get(CONF_SCAN_INTERVAL_DETAILS, DEFAULT_SCAN_INTERVAL_DETAILS)
        ),
        CONF_SCAN_INTERVAL_SUMMARY: int(
            user_input.get(CONF_SCAN_INTERVAL_SUMMARY, DEFAULT_SCAN_INTERVAL_SUMMARY)
        ),
        CONF_STALE_THRESHOLD_MINUTES: int(
            user_input.get(
                CONF_STALE_THRESHOLD_MINUTES, DEFAULT_STALE_THRESHOLD_MINUTES
            )
        ),
    }

    return data, errors


def _defaults_from_entry(
    entry: config_entries.ConfigEntry,
    user_input: dict[str, Any] | None,
) -> dict[str, Any]:
    if user_input is not None:
        return _defaults_from_input(user_input)

    merged = {**entry.data, **entry.options}
    headers = dict(merged.get(CONF_HEADERS, {}))
    api_key = headers.pop("x-api-key", "")

    return {
        CONF_CHARGER_IDS: ",".join(str(item) for item in merged.get(CONF_CHARGER_IDS, [])),
        CONF_API_BASE_URL: merged.get(CONF_API_BASE_URL, DEFAULT_API_BASE_URL),
        CONF_API_KEY: api_key,
        CONF_HEADERS_JSON: json.dumps(headers) if headers else "",
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


def _defaults_from_input(user_input: dict[str, Any] | None) -> dict[str, Any]:
    user_input = user_input or {}
    return {
        CONF_CHARGER_IDS: str(user_input.get(CONF_CHARGER_IDS, "")).strip(),
        CONF_API_BASE_URL: str(
            user_input.get(CONF_API_BASE_URL, DEFAULT_API_BASE_URL)
        ).strip(),
        CONF_API_KEY: str(user_input.get(CONF_API_KEY, "")).strip(),
        CONF_HEADERS_JSON: str(user_input.get(CONF_HEADERS_JSON, "")).strip(),
        CONF_SCAN_INTERVAL_DETAILS: int(
            user_input.get(CONF_SCAN_INTERVAL_DETAILS, DEFAULT_SCAN_INTERVAL_DETAILS)
        ),
        CONF_SCAN_INTERVAL_SUMMARY: int(
            user_input.get(CONF_SCAN_INTERVAL_SUMMARY, DEFAULT_SCAN_INTERVAL_SUMMARY)
        ),
        CONF_STALE_THRESHOLD_MINUTES: int(
            user_input.get(
                CONF_STALE_THRESHOLD_MINUTES, DEFAULT_STALE_THRESHOLD_MINUTES
            )
        ),
    }
