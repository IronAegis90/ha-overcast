"""Overcast: Home Assistant notifications as toasts on Vega OS Fire TVs."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from . import services, websocket
from .const import DOMAIN
from .hub import OvercastHub

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.NOTIFY]

type OvercastConfigEntry = ConfigEntry[OvercastHub]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the WebSocket commands and actions."""
    websocket.async_setup(hass)
    services.async_setup(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OvercastConfigEntry) -> bool:
    """Set up Overcast from a config entry."""
    hub = OvercastHub(hass, entry)
    await hub.async_load()
    entry.runtime_data = hub
    hass.data[DOMAIN] = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OvercastConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        hass.data.pop(DOMAIN, None)
    return unloaded


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OvercastConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Let the user delete a TV. It comes back if it connects again."""
    for domain, device_id in device_entry.identifiers:
        if domain == DOMAIN:
            entry.runtime_data.async_forget(device_id)
    return True
