"""Binary sensors for EV Occupancy."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DetailsCoordinator, DetailsData


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict | None = None,
) -> None:
    """Set up EV Occupancy binary sensors from YAML."""
    data = hass.data[DOMAIN]["yaml"]
    async_add_entities(_build_entities(data["charger_ids"], data["details_coordinator"]))


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EV Occupancy binary sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(_build_entities(data["charger_ids"], data["details_coordinator"]))


class EvOccupancyStaleSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating stale data."""

    def __init__(
        self,
        *,
        charger_id: int,
        coordinator: DetailsCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self._charger_id = charger_id
        self._attr_unique_id = f"{charger_id}_data_stale"
        self._attr_has_entity_name = True
        self._attr_name = "Data Stale"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        details = self._details_data
        if details is None:
            return None
        return details.data_stale

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
        coordinator = self.coordinator
        if coordinator.data:
            return coordinator.data.get(self._charger_id)
        return None


def _build_entities(
    charger_ids: list[int],
    details_coordinator: DetailsCoordinator,
) -> list[BinarySensorEntity]:
    entities: list[BinarySensorEntity] = []
    for charger_id in charger_ids:
        entities.append(
            EvOccupancyStaleSensor(
                charger_id=charger_id,
                coordinator=details_coordinator,
            )
        )
    return entities
