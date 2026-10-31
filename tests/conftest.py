"""Fixtures for Overcast tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import MockHAClientWebSocket

from custom_components.overcast.const import DOMAIN, PROTOCOL_VERSION
from homeassistant.core import HomeAssistant

DEVICE_ID = "6f1c2c7e-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


@pytest.fixture
async def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Overcast config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Overcast")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


Connect = Callable[..., Awaitable[tuple[MockHAClientWebSocket, int]]]


@pytest.fixture
def connect_tv(hass: HomeAssistant, hass_ws_client) -> Connect:
    """Connect a fake TV; returns the client and its subscription id."""

    async def _connect(**overrides: Any) -> tuple[MockHAClientWebSocket, int]:
        client = await hass_ws_client(hass)
        msg = {
            "type": "overcast/register",
            "protocol": PROTOCOL_VERSION,
            "device_id": DEVICE_ID,
            "name": "Living Room TV",
            "app_version": "0.1.0",
            **overrides,
        }
        await client.send_json_auto_id(msg)
        result = await client.receive_json()
        assert result["success"], result
        await hass.async_block_till_done()
        return client, result["id"]

    return _connect
