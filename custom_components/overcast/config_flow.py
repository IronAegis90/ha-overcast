"""Config flow for Overcast."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class OvercastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single Overcast entry. TVs add themselves when they connect."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup."""
        if user_input is not None:
            return self.async_create_entry(title="Overcast", data={})
        return self.async_show_form(step_id="user")
