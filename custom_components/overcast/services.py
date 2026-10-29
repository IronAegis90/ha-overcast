"""The overcast.send_notification action."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_DURATION,
    ATTR_ICON_SIZE,
    ATTR_IMAGE_ENTITY,
    ATTR_IMAGE_URL,
    ATTR_LAUNCH_TITLE,
    ATTR_LAUNCH_URI,
    ATTR_MESSAGE,
    ATTR_TITLE,
    ATTR_TTL,
    DEFAULT_DURATION,
    DEFAULT_ICON_SIZE,
    DEFAULT_LAUNCH_TITLE,
    DEFAULT_TITLE,
    DEFAULT_TTL,
    DOMAIN,
    ICON_SIZES,
    SERVICE_SEND_NOTIFICATION,
    SIGNED_URL_EXPIRY,
)

# The toast renderer is a separate process that fetches the icon itself, with
# no auth headers, and draws nothing for http, data: or package URLs.
_https_url = vol.All(cv.url, vol.Match(r"^https://", msg="must be an https URL"))

SEND_NOTIFICATION_SCHEMA: VolDictType = {
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_TITLE): cv.string,
    vol.Optional(ATTR_DURATION, default=DEFAULT_DURATION): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=300)
    ),
    vol.Exclusive(ATTR_IMAGE_URL, "image"): _https_url,
    vol.Exclusive(ATTR_IMAGE_ENTITY, "image"): cv.entity_domain(["camera", "image"]),
    vol.Optional(ATTR_ICON_SIZE, default=DEFAULT_ICON_SIZE): vol.In(ICON_SIZES),
    vol.Optional(ATTR_LAUNCH_URI): cv.string,
    vol.Optional(ATTR_LAUNCH_TITLE, default=DEFAULT_LAUNCH_TITLE): cv.string,
    vol.Optional(ATTR_TTL, default=DEFAULT_TTL): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=3600)
    ),
}


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the Overcast actions."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_NOTIFICATION,
        entity_domain=NOTIFY_DOMAIN,
        schema=SEND_NOTIFICATION_SCHEMA,
        func="async_send_notification",
    )


def build_notification(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Build the notification payload sent to the TV (see PROTOCOL.md)."""
    notification: dict[str, Any] = {
        "title": data.get(ATTR_TITLE) or DEFAULT_TITLE,
        "message": data[ATTR_MESSAGE],
        "duration": data.get(ATTR_DURATION, DEFAULT_DURATION),
    }
    if url := _icon_url(hass, data):
        notification["icon"] = {
            "url": url,
            "size": data.get(ATTR_ICON_SIZE, DEFAULT_ICON_SIZE),
        }
    if uri := data.get(ATTR_LAUNCH_URI):
        notification["launch"] = {
            "uri": uri,
            "title": data.get(ATTR_LAUNCH_TITLE, DEFAULT_LAUNCH_TITLE),
        }
    return notification


def _icon_url(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Return an https URL the TV's renderer can fetch without credentials."""
    if url := data.get(ATTR_IMAGE_URL):
        return url
    if (entity_id := data.get(ATTR_IMAGE_ENTITY)) is None:
        return None
    try:
        base = get_url(hass, require_ssl=True, prefer_external=True)
    except NoURLAvailableError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_https_url"
        ) from err
    proxy = (
        "camera_proxy" if split_entity_id(entity_id)[0] == "camera" else "image_proxy"
    )
    # The camera proxy serves the snapshot at the time the TV fetches it.
    path = async_sign_path(
        hass, f"/api/{proxy}/{entity_id}", SIGNED_URL_EXPIRY, use_content_user=True
    )
    return f"{base}{path}"
