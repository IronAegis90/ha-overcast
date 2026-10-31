"""Tests for TV registration and notification delivery."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.overcast import async_remove_config_entry_device
from custom_components.overcast.const import DOMAIN
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_ID, Connect

NOTIFY_ENTITY = "notify.living_room_tv"
CONNECTED_ENTITY = "binary_sensor.living_room_tv_connectivity"


async def send_message(
    hass: HomeAssistant, message: str, title: str | None = None
) -> None:
    data = {ATTR_ENTITY_ID: NOTIFY_ENTITY, ATTR_MESSAGE: message}
    if title:
        data[ATTR_TITLE] = title
    await hass.services.async_call(
        NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE, data, blocking=True
    )


async def send_notification(hass: HomeAssistant, **data) -> None:
    await hass.services.async_call(
        DOMAIN,
        "send_notification",
        {ATTR_ENTITY_ID: NOTIFY_ENTITY, **data},
        blocking=True,
    )


async def test_register_creates_device_and_entities(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """A TV that registers gets a device, a notify entity and a connectivity sensor."""
    await connect_tv(model="Fire TV Stick 4K Select")

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, DEVICE_ID)})
    assert device is not None
    assert device.name == "Living Room TV"
    assert device.model == "Fire TV Stick 4K Select"
    assert device.sw_version == "0.1.0"

    assert hass.states.get(NOTIFY_ENTITY) is not None
    assert hass.states.get(CONNECTED_ENTITY).state == STATE_ON


async def test_send_message_reaches_tv(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """notify.send_message is delivered as an event on the TV's subscription."""
    client, sub_id = await connect_tv()

    await send_message(hass, "Motion detected", "Front door")
    msg = await client.receive_json()
    assert msg["id"] == sub_id
    assert msg["type"] == "event"
    event = msg["event"]
    assert event["kind"] == "notification"
    assert event["title"] == "Front door"
    assert event["message"] == "Motion detected"
    assert event["duration"] == 8
    assert "icon" not in event and "launch" not in event
    assert event["nid"] and event["expires_at"]

    await client.send_json_auto_id(
        {
            "type": "overcast/ack",
            "device_id": DEVICE_ID,
            "nid": event["nid"],
            "status": "posted",
        }
    )
    assert (await client.receive_json())["success"]


async def test_send_message_default_title(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """A message without a title gets the default one (toasts need a title)."""
    client, _ = await connect_tv()
    await send_message(hass, "Hello")
    assert (await client.receive_json())["event"]["title"] == "Home Assistant"


async def test_send_notification_full(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """overcast.send_notification carries icon, duration and launch action."""
    client, _ = await connect_tv()
    await send_notification(
        hass,
        message="Doorbell",
        duration=20,
        image_url="https://example.com/bell.png",
        icon_size="large",
        launch_uri="pkg://com.example.app.main",
    )
    event = (await client.receive_json())["event"]
    assert event["duration"] == 20
    assert event["icon"] == {"url": "https://example.com/bell.png", "size": "large"}
    assert event["launch"] == {"uri": "pkg://com.example.app.main", "title": "Open"}


async def test_image_url_must_be_https(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """The renderer cannot draw http icons, so they are rejected up front."""
    await connect_tv()
    with pytest.raises(Exception, match="https"):
        await send_notification(hass, message="x", image_url="http://example.com/a.png")


async def test_image_entity_signed_url(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """A camera becomes a signed https URL on the external URL."""
    client, _ = await connect_tv()

    with pytest.raises(ServiceValidationError):
        await send_notification(hass, message="x", image_entity="camera.front_door")

    await hass.config.async_update(external_url="https://example.ui.nabu.casa")
    await send_notification(hass, message="x", image_entity="camera.front_door")
    url = (await client.receive_json())["event"]["icon"]["url"]
    assert url.startswith(
        "https://example.ui.nabu.casa/api/camera_proxy/camera.front_door?authSig="
    )


async def test_queue_while_disconnected(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """Notifications for a disconnected TV are queued and delivered on reconnect."""
    client, _ = await connect_tv()
    await client.close()
    await hass.async_block_till_done()
    assert hass.states.get(CONNECTED_ENTITY).state == STATE_OFF
    # The notify entity stays available so actions are not skipped.
    assert hass.states.get(NOTIFY_ENTITY).state != "unavailable"

    await send_message(hass, "first")
    await send_message(hass, "second")
    with pytest.raises(HomeAssistantError):
        await send_notification(hass, message="not queued", ttl=0)

    client, sub_id = await connect_tv()
    assert hass.states.get(CONNECTED_ENTITY).state == STATE_ON
    first = await client.receive_json()
    second = await client.receive_json()
    assert first["id"] == sub_id
    assert [first["event"]["message"], second["event"]["message"]] == [
        "first",
        "second",
    ]


async def test_short_ttl_not_extended_while_queued(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect, freezer
) -> None:
    """A queued notification expires after its own ttl, not the 30 s live floor."""
    client, _ = await connect_tv()
    await client.close()
    await hass.async_block_till_done()

    await send_notification(hass, message="short", ttl=5)
    await send_notification(hass, message="long", ttl=60)
    freezer.tick(10)

    client, _ = await connect_tv()
    event = (await client.receive_json())["event"]
    assert event["message"] == "long"
    await client.send_json_auto_id({"type": "ping"})
    assert (await client.receive_json())["type"] == "pong"


async def test_queued_image_signed_on_delivery(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect, freezer
) -> None:
    """A queued camera image gets a fresh signed URL when it is delivered."""
    await hass.config.async_update(external_url="https://example.ui.nabu.casa")
    client, _ = await connect_tv()
    await client.close()
    await hass.async_block_till_done()

    await send_notification(
        hass, message="x", image_entity="camera.front_door", ttl=1800
    )
    freezer.tick(600)  # longer than the 5 minute signature lifetime

    client, _ = await connect_tv()
    url = (await client.receive_json())["event"]["icon"]["url"]
    token = parse_qs(urlparse(url).query)["authSig"][0]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] > dt_util.utcnow().timestamp()


async def test_device_bound_to_registering_user(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    connect_tv: Connect,
    hass_ws_client,
    hass_read_only_access_token: str,
) -> None:
    """Another user cannot take over a TV by registering with its device_id."""
    tv, sub_id = await connect_tv()

    other = await hass_ws_client(hass, hass_read_only_access_token)
    await other.send_json_auto_id(
        {
            "type": "overcast/register",
            "protocol": 1,
            "device_id": DEVICE_ID,
            "name": "Hijack",
        }
    )
    msg = await other.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"

    # The TV keeps its subscription.
    await send_message(hass, "still mine")
    msg = await tv.receive_json()
    assert msg["id"] == sub_id
    assert msg["event"]["message"] == "still mine"


async def test_protocol_mismatch(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client
) -> None:
    """A TV speaking another protocol version is refused."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "overcast/register",
            "protocol": 99,
            "device_id": DEVICE_ID,
            "name": "TV",
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unsupported_protocol"


async def test_unload_asks_tv_to_reconnect(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """Unloading tells connected TVs to reconnect."""
    client, sub_id = await connect_tv()
    assert await hass.config_entries.async_unload(entry.entry_id)
    msg = await client.receive_json()
    assert msg["id"] == sub_id
    assert msg["event"] == {"kind": "reconnect"}


async def test_entities_restored_after_restart(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """Known TVs get their entities back on reload, before they reconnect."""
    client, _ = await connect_tv()
    await client.close()
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(NOTIFY_ENTITY) is not None
    assert hass.states.get(CONNECTED_ENTITY).state == STATE_OFF


async def test_remove_device(
    hass: HomeAssistant, entry: MockConfigEntry, connect_tv: Connect
) -> None:
    """Removing a TV deletes its entities and forgets it."""
    client, _ = await connect_tv()
    await client.close()
    await hass.async_block_till_done()

    # What HA's config/device_registry/remove_config_entry command does.
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, DEVICE_ID)})
    assert await async_remove_config_entry_device(hass, entry, device)
    dr.async_get(hass).async_update_device(
        device.id, remove_config_entry_id=entry.entry_id
    )
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get(NOTIFY_ENTITY) is None
    assert entry.runtime_data.devices == {}
