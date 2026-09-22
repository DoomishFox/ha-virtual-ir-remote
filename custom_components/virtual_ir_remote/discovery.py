"""Discover MQTT infrared emitters in Home Assistant's registries."""

from homeassistant.components import infrared
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er


@callback
def async_find_emitter(hass: HomeAssistant, device_id: str) -> er.RegistryEntry | None:
    """Find the single enabled MQTT emitter on the selected device."""
    if dr.async_get(hass).async_get(device_id) is None:
        return None
    emitters = [
        entry
        for entry in er.async_entries_for_device(er.async_get(hass), device_id)
        if entry.platform == MQTT_DOMAIN
        and entry.domain == infrared.DOMAIN
        and entry.disabled_by is None
        and entry.original_device_class == infrared.InfraredDeviceClass.EMITTER
    ]
    return emitters[0] if len(emitters) == 1 else None
