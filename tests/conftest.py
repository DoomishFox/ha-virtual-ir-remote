"""Common fixtures for the IR Remote tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import (
    MqttMockHAClient,
    MqttMockPahoClient,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.virtual_ir_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def enable_integration(enable_custom_integrations: None) -> None:
    """Load the custom integration in every Home Assistant test."""


@pytest.fixture
async def mqtt_mock(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mqtt_client_mock: MqttMockPahoClient,
) -> AsyncGenerator[MqttMockHAClient]:
    """Unload the mocked MQTT entry so its periodic timers are cleaned up."""
    yield mqtt_mock
    for entry in hass.config_entries.async_entries("mqtt"):
        await hass.config_entries.async_unload(entry.entry_id)
    # The upstream fake disconnect does not emit Paho's socket-close callback.
    mqtt_client_mock.on_socket_close(
        mqtt_client_mock, None, Mock(fileno=Mock(return_value=-1))
    )
    await hass.async_block_till_done()
