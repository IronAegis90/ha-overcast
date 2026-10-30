# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately, not in a public issue:
**[Report a vulnerability](https://github.com/IronAegis90/ha-overcast/security/advisories/new)** (GitHub private vulnerability reporting).

Include what you found, how to reproduce it, and the Home Assistant and Overcast versions. You should get a reply within a week. Please give a fix time to ship before you disclose publicly.

## Scope

In scope: the `overcast` integration in this repository. That covers its WebSocket commands (`overcast/register`, `overcast/ack`), the `overcast.send_notification` action, and the signed camera/image URLs it creates.

Out of scope: Home Assistant itself, HACS, and the Vega OS toast renderer. Report those to their projects. Vulnerabilities in the TV app go to [overcast-tv](https://github.com/IronAegis90/overcast-tv/security/advisories/new).

## Supported versions

Only the latest release gets security fixes.

## Keeping your setup safe

- Give each TV a token from its own dedicated **non-admin** Home Assistant user. Overcast's commands don't need admin rights. A TV can only be taken over with a token for the user it is registered to, so one user per TV keeps a leaked token from affecting your other TVs.
- If a TV is lost or sold, or a token may have leaked, **deactivate that user** (Settings → People → Users) and revoke **all** of its tokens, not just the TV's. Anyone holding a token can create more long-lived tokens for the same user. Then delete the TV's device in Home Assistant. Give the remaining TVs a new user, and new tokens.
- Never paste a long-lived access token into an issue, log or screenshot.
