"""Config flow for the Gemini HA integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_API_KEY,
    CONF_CHAT_MODEL,
    CONF_STT_LANGUAGE,
    CONF_TTS_VOICE,
    DEFAULT_CHAT_MODEL,
    DEFAULT_STT_LANGUAGE,
    DEFAULT_TTS_VOICE,
    DOMAIN,
    SUPPORTED_STT_LANGUAGES,
    SUPPORTED_TTS_VOICES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def _validate_api_key(hass: HomeAssistant, api_key: str) -> None:
    """Validate the Gemini API key by listing available models."""
    from google import genai  # noqa: PLC0415

    client = genai.Client(api_key=api_key)
    await hass.async_add_executor_job(lambda: list(client.models.list()))


class GeminiHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Gemini HA."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user step to collect the API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            try:
                await _validate_api_key(self.hass, user_input[CONF_API_KEY])
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error validating Gemini API key")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Gemini HA",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                    options={
                        CONF_CHAT_MODEL: DEFAULT_CHAT_MODEL,
                        CONF_STT_LANGUAGE: DEFAULT_STT_LANGUAGE,
                        CONF_TTS_VOICE: DEFAULT_TTS_VOICE,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GeminiHAOptionsFlow:
        """Return the options flow handler."""
        return GeminiHAOptionsFlow(config_entry)


class GeminiHAOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Gemini HA – lets the user change model, voice, and STT language."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialise the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Gemini HA options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CHAT_MODEL,
                        default=options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
                    ): str,
                    vol.Optional(
                        CONF_STT_LANGUAGE,
                        default=options.get(CONF_STT_LANGUAGE, DEFAULT_STT_LANGUAGE),
                    ): vol.In(SUPPORTED_STT_LANGUAGES),
                    vol.Optional(
                        CONF_TTS_VOICE,
                        default=options.get(CONF_TTS_VOICE, DEFAULT_TTS_VOICE),
                    ): vol.In(SUPPORTED_TTS_VOICES),
                }
            ),
        )
