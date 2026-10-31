"""WebSocket commands the Overcast TV app uses (see PROTOCOL.md)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, PROTOCOL_VERSION
from .hub import OvercastHub


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the Overcast WebSocket commands."""
    websocket_api.async_register_command(hass, ws_register)
    websocket_api.async_register_command(hass, ws_ack)


def _get_hub(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg_id: int
) -> OvercastHub | None:
    if (hub := hass.data.get(DOMAIN)) is None:
        connection.send_error(
            msg_id, "not_loaded", "The Overcast integration is not set up"
        )
    return hub


@websocket_api.websocket_command(
    {
        vol.Required("type"): "overcast/register",
        vol.Required("protocol"): int,
        vol.Required("device_id"): vol.All(str, vol.Length(min=1, max=64)),
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=64)),
        vol.Optional("app_version"): str,
        vol.Optional("model"): str,
        vol.Optional("capabilities", default={}): dict,
    }
)
@callback
def ws_register(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Register a TV and keep the subscription open for its notifications."""
    if (hub := _get_hub(hass, connection, msg["id"])) is None:
        return
    if msg["protocol"] != PROTOCOL_VERSION:
        connection.send_error(
            msg["id"],
            "unsupported_protocol",
            f"This Home Assistant speaks Overcast protocol {PROTOCOL_VERSION}",
        )
        return

    device_id = msg["device_id"]
    # Device ids are visible to every signed-in user (device registry), so a TV
    # stays bound to the user it first registered with; otherwise any user could
    # take over its subscription and read its notifications.
    owner = hub.owner(device_id)
    if owner is not None and owner != connection.user.id:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNAUTHORIZED,
            "This TV is registered to another Home Assistant user. Delete its "
            "device in Home Assistant to register it with this user.",
        )
        return
    info = {
        "user_id": connection.user.id,
        "name": msg["name"],
        "model": msg.get("model"),
        "app_version": msg.get("app_version"),
        "capabilities": msg["capabilities"],
    }
    connection.subscriptions[msg["id"]] = hub.async_register(
        connection, msg["id"], device_id, info
    )
    connection.send_result(msg["id"], {"protocol": PROTOCOL_VERSION})
    hub.async_flush(device_id)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "overcast/ack",
        vol.Required("device_id"): str,
        vol.Required("nid"): str,
        vol.Required("status"): vol.In(["posted", "failed", "expired"]),
        vol.Optional("error"): str,
    }
)
@callback
def ws_ack(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Receive the TV's report on a notification."""
    if (hub := _get_hub(hass, connection, msg["id"])) is None:
        return
    hub.async_ack(msg["device_id"], msg["nid"], msg["status"], msg.get("error"))
    connection.send_result(msg["id"])
