"""Gemini HA integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, INTEGRATION_VERSION, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gemini HA from a config entry."""
    _LOGGER.debug(
        "Setting up Gemini HA entry %s (integration version %s, config entry version %s.%s)",
        entry.entry_id,
        INTEGRATION_VERSION,
        entry.version,
        entry.minor_version,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    _LOGGER.info(
        "Gemini HA entry %s set up successfully (platforms: %s)",
        entry.entry_id,
        ", ".join(PLATFORMS),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Gemini HA config entry."""
    _LOGGER.debug("Unloading Gemini HA entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.debug("Gemini HA entry %s unloaded successfully", entry.entry_id)
    else:
        _LOGGER.warning("Gemini HA entry %s failed to unload cleanly", entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry to the current schema version."""
    _LOGGER.debug(
        "Migrating Gemini HA entry %s from version %s.%s",
        entry.entry_id,
        entry.version,
        entry.minor_version,
    )

    # Future migrations go here as VERSION / MINOR_VERSION is incremented.
    # Example pattern:
    #   if entry.version == 1 and entry.minor_version < 2:
    #       new_data = {**entry.data, "new_key": "default"}
    #       hass.config_entries.async_update_entry(entry, data=new_data, minor_version=2)

    _LOGGER.info(
        "Gemini HA entry %s migration complete (now at version %s.%s)",
        entry.entry_id,
        entry.version,
        entry.minor_version,
    )
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    _LOGGER.debug("Options changed for Gemini HA entry %s — reloading", entry.entry_id)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
