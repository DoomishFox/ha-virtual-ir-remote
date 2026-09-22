"""Tests for Virtual IR Remote lifecycle."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.virtual_ir_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mqtt_mock")


async def test_reload_and_unload_entry(hass: HomeAssistant) -> None:
    """Each blaster owns one Remote; changes reload it and unloading removes it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bedroom",
        unique_id="device",
        data={
            CONF_DEVICE_ID: "device",
            CONF_INFRARED_ENTITY_ID: "emitter",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert hass.states.get("remote.bedroom") is not None
    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as reload:
        hass.config_entries.async_update_entry(entry, title="Renamed")
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    state = hass.states.get("remote.bedroom")
    assert state is not None
    assert state.attributes["restored"] is True
