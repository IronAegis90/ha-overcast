"""Notify entity for each Overcast TV."""

from __future__ import annotations

from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_TTL, DEFAULT_TTL, SIGNAL_NEW_DEVICE
from .entity import OvercastEntity
from .hub import OvercastHub
from .services import build_notification


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OvercastHub],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a notify entity for every registered TV."""
    hub = entry.runtime_data
    async_add_entities(OvercastNotifyEntity(hub, d) for d in hub.devices)

    @callback
    def _add(device_id: str) -> None:
        async_add_entities([OvercastNotifyEntity(hub, device_id)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE.format(entry.entry_id), _add)
    )


class OvercastNotifyEntity(OvercastEntity, NotifyEntity):
    """Shows notifications as toasts on the TV.

    The entity stays available while the TV is disconnected (HA skips
    unavailable entities in action calls), so notifications sent then are
    queued. Connectivity is reported by the TV's binary sensor instead.
    """

    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, hub: OvercastHub, device_id: str) -> None:
        super().__init__(hub, device_id)
        self._attr_unique_id = device_id

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Handle notify.send_message."""
        notification = build_notification(
            self.hass, {"message": message, "title": title}
        )
        self.hub.async_send(self.device_id, notification, DEFAULT_TTL)

    async def async_send_notification(self, **data: Any) -> None:
        """Handle overcast.send_notification."""
        notification = build_notification(self.hass, data)
        self.hub.async_send(self.device_id, notification, data[ATTR_TTL])
