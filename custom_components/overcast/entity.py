"""Base entity for an Overcast TV."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import DEFAULT_MODEL, OvercastHub


class OvercastEntity(Entity):
    """An entity that belongs to one registered TV."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: OvercastHub, device_id: str) -> None:
        self.hub = hub
        self.device_id = device_id
        info = hub.devices[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Amazon",
            model=info.get("model") or DEFAULT_MODEL,
            name=info["name"],
            sw_version=info.get("app_version"),
        )
