"""Connectivity sensor for each Overcast TV."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_DEVICE_UPDATE, SIGNAL_NEW_DEVICE
from .entity import OvercastEntity
from .hub import OvercastHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OvercastHub],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a connectivity sensor for every registered TV."""
    hub = entry.runtime_data
    async_add_entities(OvercastConnectedSensor(hub, d) for d in hub.devices)

    @callback
    def _add(device_id: str) -> None:
        async_add_entities([OvercastConnectedSensor(hub, device_id)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE.format(entry.entry_id), _add)
    )


class OvercastConnectedSensor(OvercastEntity, BinarySensorEntity):
    """On while the TV app holds its connection to Home Assistant."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: OvercastHub, device_id: str) -> None:
        super().__init__(hub, device_id)
        self._attr_unique_id = f"{device_id}_connected"

    @property
    def is_on(self) -> bool:
        return self.hub.is_connected(self.device_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_DEVICE_UPDATE.format(self.device_id),
                self.async_write_ha_state,
            )
        )
