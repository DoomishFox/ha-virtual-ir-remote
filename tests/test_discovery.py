"""Test emitter selection without vendor-specific or text fallbacks."""

import pytest
from custom_components.virtual_ir_remote.discovery import async_find_emitter
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.parametrize(
    ("domain", "platform", "device_class", "count", "expected"),
    [
        pytest.param("infrared", "mqtt", "emitter", 1, True, id="mqtt-emitter"),
        pytest.param("infrared", "mqtt", "emitter", 2, False, id="ambiguous"),
        pytest.param("infrared", "mqtt", "receiver", 1, False, id="receiver"),
        pytest.param("infrared", "other", "emitter", 1, False, id="not-mqtt"),
        pytest.param("text", "mqtt", None, 1, False, id="text-only"),
        pytest.param("infrared", "mqtt", "emitter", 0, False, id="no-emitter"),
    ],
)
async def test_find_emitter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    domain: str,
    platform: str,
    device_class: str | None,
    count: int,
    expected: bool,
) -> None:
    """Accept exactly one MQTT emitter, regardless of blaster manufacturer."""
    entry = MockConfigEntry(domain="mqtt")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("mqtt", "generic-emitter")},
        manufacturer="Generic manufacturer",
    )
    for index in range(count):
        entity_registry.async_get_or_create(
            domain,
            platform,
            str(index),
            device_id=device.id,
            config_entry=entry,
            original_device_class=device_class,
        )
    assert (async_find_emitter(hass, device.id) is not None) is expected


async def test_missing_device(hass: HomeAssistant) -> None:
    """A deleted device cannot be selected."""
    assert async_find_emitter(hass, "missing") is None
