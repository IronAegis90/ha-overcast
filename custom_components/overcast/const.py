"""Constants for the Overcast integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "overcast"

# Version of the TV <-> integration message schema (see PROTOCOL.md).
PROTOCOL_VERSION: Final = 1

STORAGE_VERSION: Final = 1

# Dispatcher signals. Format with the config entry id / TV device id.
SIGNAL_NEW_DEVICE: Final = f"{DOMAIN}_new_device_{{}}"
SIGNAL_DEVICE_UPDATE: Final = f"{DOMAIN}_device_update_{{}}"

SERVICE_SEND_NOTIFICATION: Final = "send_notification"

ATTR_MESSAGE: Final = "message"
ATTR_TITLE: Final = "title"
ATTR_DURATION: Final = "duration"
ATTR_IMAGE_URL: Final = "image_url"
ATTR_IMAGE_ENTITY: Final = "image_entity"
ATTR_ICON_SIZE: Final = "icon_size"
ATTR_LAUNCH_URI: Final = "launch_uri"
ATTR_LAUNCH_TITLE: Final = "launch_title"
ATTR_TTL: Final = "ttl"

ICON_SIZES: Final = ["small", "normal", "large"]

DEFAULT_TITLE: Final = "Home Assistant"
DEFAULT_DURATION: Final = 8
DEFAULT_ICON_SIZE: Final = "normal"
DEFAULT_LAUNCH_TITLE: Final = "Open"
# How long a notification for a disconnected TV is kept, in seconds.
DEFAULT_TTL: Final = 60
# A notification delivered live still carries an expiry so a TV that buffers it
# (or has a skewed clock) does not show it much later.
MIN_EXPIRY: Final = timedelta(seconds=30)
# Notifications kept per disconnected TV; the oldest is dropped first.
QUEUE_SIZE: Final = 10

# Lifetime of signed camera/image URLs. The toast renderer fetches the icon
# right away, so this only needs to cover delivery and queueing.
SIGNED_URL_EXPIRY: Final = timedelta(minutes=5)
