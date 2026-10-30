"""Tracks the TVs that registered with Overcast and delivers notifications to them."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.ulid import ulid_now

from .const import (
    DOMAIN,
    MIN_EXPIRY,
    QUEUE_SIZE,
    SIGNAL_DEVICE_UPDATE,
    SIGNAL_NEW_DEVICE,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "Fire TV (Vega OS)"


# Returns the notification fields (see PROTOCOL.md); called again on delivery.
type NotificationBuilder = Callable[[], dict[str, Any]]


@dataclass(slots=True)
class _Subscriber:
    """The WebSocket subscription a connected TV receives notifications on."""

    connection: websocket_api.ActiveConnection
    msg_id: int

    @callback
    def send(self, payload: dict[str, Any]) -> None:
        self.connection.send_message(websocket_api.event_message(self.msg_id, payload))


def _payload(
    nid: str, expires_at: datetime, notification: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": "notification",
        "nid": nid,
        "expires_at": expires_at.isoformat(),
        **notification,
    }


class OvercastHub:
    """Registry of TVs, their live connections and their pending notifications."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.devices: dict[str, dict[str, Any]] = {}
        self._store: Store[dict[str, dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._subscribers: dict[str, _Subscriber] = {}
        # Per TV: (expiry, nid, build) for notifications waiting for it to connect.
        # They are rebuilt on delivery so signed image URLs are fresh.
        self._queues: dict[str, deque[tuple[datetime, str, NotificationBuilder]]] = {}

    async def async_load(self) -> None:
        """Load the TVs registered in earlier runs."""
        self.devices = await self._store.async_load() or {}

    async def async_shutdown(self) -> None:
        """Save the TV list and ask connected TVs to reconnect.

        Their subscriptions die with the hub; the TVs re-register with the next one.
        """
        await self._store.async_save(self.devices)
        for device_id, subscriber in list(self._subscribers.items()):
            subscriber.send({"kind": "reconnect"})
            subscriber.connection.subscriptions.pop(subscriber.msg_id, None)
            del self._subscribers[device_id]

    def owner(self, device_id: str) -> str | None:
        """Return the id of the HA user the TV registered with, if known."""
        return self.devices.get(device_id, {}).get("user_id")

    def is_connected(self, device_id: str) -> bool:
        """Return whether the TV currently holds a connection."""
        return device_id in self._subscribers

    @callback
    def async_register(
        self,
        connection: websocket_api.ActiveConnection,
        msg_id: int,
        device_id: str,
        info: dict[str, Any],
    ) -> CALLBACK_TYPE:
        """Attach a TV's subscription; returns the callback that detaches it."""
        is_new = device_id not in self.devices
        if self.devices.get(device_id) != info:
            self.devices[device_id] = info
            self._store.async_delay_save(lambda: self.devices, 1)

        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, device_id)},
            manufacturer="Amazon",
            model=info.get("model") or DEFAULT_MODEL,
            name=info["name"],
            sw_version=info.get("app_version"),
        )

        # A TV that reconnects before HA notices the old socket closed replaces it.
        subscriber = _Subscriber(connection, msg_id)
        self._subscribers[device_id] = subscriber

        if is_new:
            async_dispatcher_send(
                self.hass, SIGNAL_NEW_DEVICE.format(self.entry.entry_id), device_id
            )
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_UPDATE.format(device_id))

        @callback
        def unsubscribe() -> None:
            if self._subscribers.get(device_id) is subscriber:
                del self._subscribers[device_id]
                async_dispatcher_send(self.hass, SIGNAL_DEVICE_UPDATE.format(device_id))

        return unsubscribe

    @callback
    def async_flush(self, device_id: str) -> None:
        """Deliver what was queued while the TV was away, dropping expired items."""
        queue = self._queues.pop(device_id, None)
        subscriber = self._subscribers.get(device_id)
        if not queue or subscriber is None:
            return
        now = dt_util.utcnow()
        for expires_at, nid, build in queue:
            if expires_at <= now:
                continue
            try:
                notification = build()
            except HomeAssistantError as err:
                _LOGGER.warning("Dropping queued notification %s: %s", nid, err)
                continue
            subscriber.send(_payload(nid, expires_at, notification))

    @callback
    def async_forget(self, device_id: str) -> None:
        """Forget a TV removed by the user. It is added again if it reconnects."""
        self.devices.pop(device_id, None)
        self._queues.pop(device_id, None)
        self._store.async_delay_save(lambda: self.devices, 1)

    @callback
    def async_send(self, device_id: str, build: NotificationBuilder, ttl: int) -> str:
        """Send a notification now, or queue it for up to ``ttl`` seconds.

        ``build`` runs now, so invalid input fails the action, and again on
        delivery for queued notifications.
        """
        nid = ulid_now()
        now = dt_util.utcnow()
        notification = build()
        if subscriber := self._subscribers.get(device_id):
            # Live sends get a floor so clock skew on the TV doesn't drop them.
            subscriber.send(
                _payload(
                    nid, now + max(timedelta(seconds=ttl), MIN_EXPIRY), notification
                )
            )
            return nid
        if ttl <= 0:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_connected",
                translation_placeholders={"name": self.devices[device_id]["name"]},
            )
        self._queues.setdefault(device_id, deque(maxlen=QUEUE_SIZE)).append(
            (now + timedelta(seconds=ttl), nid, build)
        )
        _LOGGER.debug("Queued %s for %s (TV not connected)", nid, device_id)
        return nid

    @callback
    def async_ack(
        self, device_id: str, nid: str, status: str, error: str | None
    ) -> None:
        """Record the TV's report on a notification it received."""
        if status == "posted":
            _LOGGER.debug("%s posted on %s", nid, device_id)
        else:
            _LOGGER.warning(
                "Notification %s %s on %s: %s",
                nid,
                status,
                self.devices.get(device_id, {}).get("name", device_id),
                error or "no details",
            )
