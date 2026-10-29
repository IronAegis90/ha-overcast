# ha-overcast

Home Assistant integration for **Overcast**, which shows Home Assistant notifications as toasts on Fire TVs running Vega OS. It replaces [Notifications for Fire TV](https://www.home-assistant.io/integrations/nfandroidtv/) (`nfandroidtv`), which needs a sideloaded Android app that Vega OS can't run.

It needs the [Overcast TV app](https://github.com/IronAegis90/overcast-tv) on each TV. The TV connects out to Home Assistant, so nothing has to reach the TV and no ports need opening.

> **Status: early development.** Nothing has been tested on real Fire TV hardware yet.

## Installation

1. In HACS, open **Custom repositories**, add `https://github.com/IronAegis90/ha-overcast` as an **Integration**, and install **Overcast**.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Overcast** and confirm.
4. Create a long-lived access token for the TVs. A dedicated non-admin user is safest: create a user named "Overcast", log in as that user, then go to **Profile → Security → Long-lived access tokens**.
5. On each TV, open the Overcast app and enter your Home Assistant URL, the token and a name for the TV.

Each TV appears as a device as soon as it connects. You don't need to add TVs one by one.

Requires Home Assistant 2025.10 or later.

## Entities

For each TV:

| Entity | Purpose |
|---|---|
| `notify.<tv name>` | Target of `notify.send_message` and `overcast.send_notification`. It stays available while the TV is offline, so notifications sent then are queued. |
| `binary_sensor.<tv name>_connectivity` | On while the TV app is connected. |

To remove a TV, delete its device. It comes back if that TV connects again.

## Sending notifications

Title and message only, with the standard notify action:

```yaml
action: notify.send_message
target:
  entity_id: notify.living_room_tv
data:
  title: Front door
  message: Someone is at the door
```

Everything else goes through `overcast.send_notification`. It can target entities, devices or areas.

```yaml
action: overcast.send_notification
target:
  entity_id: notify.living_room_tv
data:
  title: Front door
  message: Someone is at the door
  duration: 15                     # seconds, 1–300 (default 8)
  image_entity: camera.front_door  # or image_url: https://…
  icon_size: large                 # small | normal | large
  launch_uri: pkg://com.example.app.main
  launch_title: Open
  ttl: 120                         # keep this long if the TV is offline (default 60, 0 = fail instead)
```

### Images

The toast shows the image as its icon. Vega's toast renderer fetches the image itself, from a separate process that can't send credentials, so:

- `image_url` must be `https://` and publicly fetchable.
- `image_entity` (a camera or image entity) is sent as a short-lived (5 minute) signed URL on your Home Assistant's **https** address: Home Assistant Cloud, or an external URL with TLS. Set one under **Settings → System → Network**. A camera URL serves the snapshot at the moment the TV fetches it, which is right after the notification arrives.

## Compared with Notifications for Fire TV

| nfandroidtv | Overcast |
|---|---|
| `title`, `message` | Same |
| `data.duration` | `duration` |
| `data.image` (url / path / auth) | `image_url` (https only, no auth) or `image_entity` |
| `data.icon` | `image_url` / `image_entity`; shown as the toast icon |
| `data.position` | Not available: Vega places toasts itself |
| `data.color`, `data.transparency`, `data.fontsize` | Not available: Vega styles toasts itself |
| `data.interrupt` | Not available. A toast never takes focus; use `launch_uri` to add an action that opens an app |
| Large image below the text | Not available: the toast API has only an icon |
| Works after the TV reboots | The Overcast app has to be opened once after each reboot (Vega has no start-on-boot for services) |

## How it works

The TV app holds a WebSocket connection to Home Assistant's API, registers with the custom `overcast/register` command, and receives notifications as events on that subscription. [PROTOCOL.md](PROTOCOL.md) documents the messages.

## Development

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt ruff
pytest
ruff check custom_components tests && ruff format --check custom_components tests
```

## License

Apache-2.0
