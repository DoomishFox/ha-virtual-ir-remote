"""The Virtual IR Remote integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

type VirtualIrRemoteConfigEntry = ConfigEntry[None]

PLATFORMS: list[Platform] = [Platform.REMOTE]


async def async_setup_entry(
    hass: HomeAssistant, entry: VirtualIrRemoteConfigEntry
) -> bool:
    """Set up Virtual IR Remote from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_async_update_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_entry(
    hass: HomeAssistant, entry: VirtualIrRemoteConfigEntry
) -> None:
    """Reload the integration when its remotes or commands change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: VirtualIrRemoteConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
