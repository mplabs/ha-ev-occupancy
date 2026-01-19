"""Sensors for EV Occupancy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DetailsCoordinator, DetailsData, SummaryCoordinator, SummaryData


@dataclass(frozen=True)
class EvOccupancySensorDescription(SensorEntityDescription):
    """Describes EV Occupancy sensor."""

    source: str | None = None


DETAILS_SENSORS: tuple[EvOccupancySensorDescription, ...] = (
    EvOccupancySensorDescription(
        key="available",
        name="Available",
        icon="mdi:ev-plug",
        state_class=SensorStateClass.MEASUREMENT,
        source="details",
    ),
    EvOccupancySensorDescription(
        key="occupied",
        name="Occupied",
        icon="mdi:ev-station",
        state_class=SensorStateClass.MEASUREMENT,
        source="details",
    ),
    EvOccupancySensorDescription(
        key="unknown",
        name="Unknown",
        icon="mdi:help-circle-outline",
        state_class=SensorStateClass.MEASUREMENT,
        source="details",
    ),
    EvOccupancySensorDescription(
        key="total",
        name="Total",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        source="details",
    ),
    EvOccupancySensorDescription(
        key="freshness_minutes",
        name="Freshness Minutes",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        source="details",
    ),
)

SUMMARY_SENSORS: tuple[EvOccupancySensorDescription, ...] = (
    EvOccupancySensorDescription(
        key="sessions_7d",
        name="Sessions 7d",
        icon="mdi:history",
        state_class=SensorStateClass.MEASUREMENT,
        source="summary",
    ),
    EvOccupancySensorDescription(
        key="sessions_30d",
        name="Sessions 30d",
        icon="mdi:history",
        state_class=SensorStateClass.MEASUREMENT,
        source="summary",
    ),
    EvOccupancySensorDescription(
        key="last_session_end",
        name="Last Session End",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-end",
        source="summary",
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict | None = None,
) -> None:
    """Set up EV Occupancy sensors from YAML."""
    data = hass.data[DOMAIN]["yaml"]
    async_add_entities(
        _build_entities(
            data["charger_ids"],
            data["details_coordinator"],
            data["summary_coordinator"],
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EV Occupancy sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        _build_entities(
            data["charger_ids"],
            data["details_coordinator"],
            data["summary_coordinator"],
        )
    )


class EvOccupancySensor(CoordinatorEntity, SensorEntity):
    """Sensor for EV Occupancy data."""

    entity_description: EvOccupancySensorDescription

    def __init__(
        self,
        *,
        charger_id: str,
        description: EvOccupancySensorDescription,
        coordinator: DetailsCoordinator | SummaryCoordinator,
        details_coordinator: DetailsCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._charger_id = charger_id
        self._details_coordinator = details_coordinator
        self._attr_unique_id = f"{charger_id}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_name = description.name

    @property
    def native_value(self) -> Any:
        if self.entity_description.source == "details":
            details = self._details_data
            if details is None:
                return None
            if self.entity_description.key == "available":
                return details.available_evses
            if self.entity_description.key == "occupied":
                return details.occupied_evses
            if self.entity_description.key == "unknown":
                return details.unknown_evses
            if self.entity_description.key == "total":
                return details.total_evses
            if self.entity_description.key == "freshness_minutes":
                return details.freshness_minutes
        else:
            summary = self._summary_data
            if summary is None:
                return None
            if self.entity_description.key == "sessions_7d":
                return summary.sessions_7d
            if self.entity_description.key == "sessions_30d":
                return summary.sessions_30d
            if self.entity_description.key == "last_session_end":
                return summary.last_session_end
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "available":
            details = self._details_data
            if details is None:
                return None
            return _details_attributes(details)

        if self.entity_description.key == "sessions_7d":
            summary = self._summary_data
            if summary is None:
                return None
            return {
                "sessions_today": summary.sessions_today,
                "peak_hour_7d": summary.peak_hour_7d,
                "peak_weekday_30d": summary.peak_weekday_30d,
            }

        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        details = self._details_data
        name = details.name if details and details.name else f"Charger {self._charger_id}"
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._charger_id))},
            name=name,
            manufacturer="Iternio",
            model="EV Charger",
        )

    @property
    def _details_data(self) -> DetailsData | None:
        if not self._details_coordinator.data:
            return None
        return self._details_coordinator.data.get(self._charger_id)

    @property
    def _summary_data(self) -> SummaryData | None:
        coordinator = self.coordinator
        if isinstance(coordinator, SummaryCoordinator) and coordinator.data:
            return coordinator.data.get(self._charger_id)
        return None


def _details_attributes(details: DetailsData) -> dict[str, Any]:
    return {
        "charger_id": details.charger_id,
        "name": details.name,
        "address": details.address,
        "network_name": details.network_name,
        "lat": details.lat,
        "lon": details.lon,
        "has_dynamic_status": details.has_dynamic_status,
        "last_status_update": details.last_status_update,
        "source": details.source,
        "evse_statuses": details.evse_statuses,
    }


def _build_entities(
    charger_ids: list[str],
    details_coordinator: DetailsCoordinator,
    summary_coordinator: SummaryCoordinator,
) -> list[SensorEntity]:
    entities: list[SensorEntity] = []
    for charger_id in charger_ids:
        for description in DETAILS_SENSORS:
            entities.append(
                EvOccupancySensor(
                    charger_id=charger_id,
                    description=description,
                    coordinator=details_coordinator,
                    details_coordinator=details_coordinator,
                )
            )
        for description in SUMMARY_SENSORS:
            entities.append(
                EvOccupancySensor(
                    charger_id=charger_id,
                    description=description,
                    coordinator=summary_coordinator,
                    details_coordinator=details_coordinator,
                )
            )
    return entities
