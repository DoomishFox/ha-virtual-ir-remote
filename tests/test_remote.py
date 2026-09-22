"""Tests for Virtual IR Remote entities."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.virtual_ir_remote.commands import NEC48Command
from custom_components.virtual_ir_remote.const import (
    ATTR_COMMANDS,
    CONF_COMMAND_ACTIONS,
    CONF_COMMAND_BYTES,
    CONF_COMMAND_NAME,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
    CommandAction,
)
from custom_components.virtual_ir_remote.remote import VirtualIrRemote
from homeassistant import config_entries
from homeassistant.components import infrared
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_ACTIVITY_LIST,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DATA_COMPONENT,
    DEFAULT_DELAY_SECS,
    SERVICE_SEND_COMMAND,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_PROTOCOL,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
)
from pytest_homeassistant_custom_component.typing import MqttMockHAClient

REMOTE_ENTITY_ID = "remote.office_ir"
EMITTER_TOPIC = "zigbee2mqtt/Office IR/set/ir_emitter"
DEVICE_NAME = "Pelonis fan"


@dataclass(frozen=True, slots=True)
class RemoteSetup:
    """Entities and command used by a configured test Remote."""

    emitter: er.RegistryEntry
    command: NEC48Command


async def _async_setup_remote(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    *,
    command_bytes: Sequence[int] = (0x03, 0x03),
    include_device_actions: bool = False,
    include_second_device: bool = False,
    include_second_command: bool = False,
) -> RemoteSetup:
    """Discover a blaster and set up a Remote using registry UUIDs."""
    device_info = {
        "identifiers": ["zigbee2mqtt_office_ir"],
        "manufacturer": "Moes",
        "model": "Universal smart IR remote control",
        "model_id": "UFO-R11",
        "name": "Office IR",
    }
    async_fire_mqtt_message(
        hass,
        "homeassistant/infrared/office_ir/ir_emitter/config",
        json.dumps(
            {
                "name": "Ir emitter",
                "unique_id": "office_ir_ir_emitter_zigbee2mqtt",
                "schema": "emitter",
                "command_topic": EMITTER_TOPIC,
                "device": device_info,
            }
        ),
    )
    await hass.async_block_till_done()

    mqtt_entry = hass.config_entries.async_entries(MQTT_DOMAIN)[0]
    device = device_registry.async_get_device_by_identifier(
        (MQTT_DOMAIN, "zigbee2mqtt_office_ir"), mqtt_entry.entry_id
    )
    assert device is not None
    device_entities = er.async_entries_for_device(entity_registry, device.id)
    emitter = next(
        entry for entry in device_entities if entry.domain == infrared.DOMAIN
    )
    command_subentries = [
        config_entries.ConfigSubentryDataWithId(
            data={
                CONF_DEVICE: DEVICE_NAME,
                CONF_COMMAND_NAME: "toggle_power",
                CONF_COMMAND_ACTIONS: [],
                CONF_PROTOCOL: "nec48",
                CONF_ADDRESS: 0x01,
                CONF_COMMAND_BYTES: list(command_bytes),
            },
            subentry_id="pelonis-power",
            subentry_type=SUBENTRY_TYPE_COMMAND,
            title="Pelonis fan: toggle_power",
            unique_id=None,
        )
    ]
    if include_second_command:
        command_subentries.append(
            config_entries.ConfigSubentryDataWithId(
                data={
                    CONF_DEVICE: DEVICE_NAME,
                    CONF_COMMAND_NAME: "toggle_speed",
                    CONF_COMMAND_ACTIONS: [],
                    CONF_PROTOCOL: "nec48",
                    CONF_ADDRESS: 0x01,
                    CONF_COMMAND_BYTES: [0x07, 0x07],
                },
                subentry_id="pelonis-speed",
                subentry_type=SUBENTRY_TYPE_COMMAND,
                title="Pelonis fan: toggle_speed",
                unique_id=None,
            )
        )
    if include_device_actions:
        command_subentries.append(
            config_entries.ConfigSubentryDataWithId(
                data={
                    CONF_DEVICE: DEVICE_NAME,
                    CONF_COMMAND_NAME: "power_toggle",
                    CONF_COMMAND_ACTIONS: [
                        CommandAction.TURN_ON,
                        CommandAction.TURN_OFF,
                    ],
                    CONF_PROTOCOL: "nec48",
                    CONF_ADDRESS: 0x01,
                    CONF_COMMAND_BYTES: [0x11, 0x11],
                },
                subentry_id="pelonis-power-toggle",
                subentry_type=SUBENTRY_TYPE_COMMAND,
                title="Pelonis fan: power_toggle",
                unique_id=None,
            )
        )
    if include_second_device:
        command_subentries.extend(
            (
                config_entries.ConfigSubentryDataWithId(
                    data={
                        CONF_DEVICE: "Television",
                        CONF_COMMAND_NAME: "volume_up",
                        CONF_COMMAND_ACTIONS: [],
                        CONF_PROTOCOL: "nec48",
                        CONF_ADDRESS: 0x02,
                        CONF_COMMAND_BYTES: [0x05, 0x05],
                    },
                    subentry_id="television-volume-up",
                    subentry_type=SUBENTRY_TYPE_COMMAND,
                    title="Television: volume_up",
                    unique_id=None,
                ),
                config_entries.ConfigSubentryDataWithId(
                    data={
                        CONF_DEVICE: "Television",
                        CONF_COMMAND_NAME: "power_on",
                        CONF_COMMAND_ACTIONS: [CommandAction.TURN_ON],
                        CONF_PROTOCOL: "nec48",
                        CONF_ADDRESS: 0x02,
                        CONF_COMMAND_BYTES: [0x09, 0x09],
                    },
                    subentry_id="television-power-on",
                    subentry_type=SUBENTRY_TYPE_COMMAND,
                    title="Television: power_on",
                    unique_id=None,
                ),
            )
        )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Office IR",
        unique_id=device.id,
        data={
            CONF_DEVICE_ID: device.id,
            CONF_INFRARED_ENTITY_ID: emitter.id,
        },
        subentries_data=command_subentries,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    return RemoteSetup(
        emitter,
        NEC48Command(address=0x01, command=[0x03, 0x03]),
    )


async def _async_send_command(
    hass: HomeAssistant,
    command: str | list[str],
    *,
    delay: float | None = None,
    include_device: bool = True,
    repeats: int | None = None,
) -> None:
    """Call the Remote send-command action."""
    service_data: dict[str, Any] = {
        ATTR_ENTITY_ID: REMOTE_ENTITY_ID,
        ATTR_COMMAND: command,
    }
    if include_device:
        service_data[ATTR_DEVICE] = DEVICE_NAME
    if delay is not None:
        service_data[ATTR_DELAY_SECS] = delay
    if repeats is not None:
        service_data[ATTR_NUM_REPEATS] = repeats
    await hass.services.async_call(
        "remote", SERVICE_SEND_COMMAND, service_data, blocking=True
    )


async def _async_call_power_action(
    hass: HomeAssistant, service: str, *, device: str | None = None
) -> None:
    """Call a standard Remote power action."""
    service_data = {ATTR_ENTITY_ID: REMOTE_ENTITY_ID}
    if device is not None:
        service_data[ATTR_ACTIVITY] = device
    await hass.services.async_call("remote", service, service_data, blocking=True)


async def test_send_named_command_after_emitter_rename(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending through the MQTT emitter after its entity ID changes."""
    setup = await _async_setup_remote(hass, mqtt_mock, device_registry, entity_registry)

    state = hass.states.get(REMOTE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_COMMANDS] == {DEVICE_NAME: ["toggle_power"]}

    entity_registry.async_update_entity(
        setup.emitter.entity_id,
        new_entity_id="infrared.renamed_ir_emitter",
    )
    await hass.async_block_till_done()

    await _async_send_command(hass, "toggle_power")

    mqtt_mock.async_publish.assert_called_once()
    publish_args = mqtt_mock.async_publish.call_args.args
    assert publish_args[0] == EMITTER_TOPIC
    assert json.loads(publish_args[1]) == {
        "timings": setup.command.get_raw_timings(),
        "modulation": 38000,
        "repeat_count": 0,
    }


async def test_turn_on_and_off_device_actions(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard Remote power actions send their assigned commands."""
    await _async_setup_remote(
        hass,
        mqtt_mock,
        device_registry,
        entity_registry,
        include_device_actions=True,
    )
    state = hass.states.get(REMOTE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_ACTIVITY_LIST] == [DEVICE_NAME]

    await _async_call_power_action(hass, SERVICE_TURN_ON)
    assert json.loads(mqtt_mock.async_publish.call_args.args[1])["timings"] == (
        NEC48Command(address=0x01, command=[0x11, 0x11]).get_raw_timings()
    )

    mqtt_mock.async_publish.reset_mock()
    await _async_call_power_action(hass, SERVICE_TURN_OFF, device=DEVICE_NAME)
    assert json.loads(mqtt_mock.async_publish.call_args.args[1])["timings"] == (
        NEC48Command(address=0x01, command=[0x11, 0x11]).get_raw_timings()
    )


async def test_power_action_requires_configured_command(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device power action must have an assigned learned command."""
    await _async_setup_remote(hass, mqtt_mock, device_registry, entity_registry)

    with pytest.raises(ServiceValidationError) as action_error:
        await _async_call_power_action(hass, SERVICE_TURN_ON, device=DEVICE_NAME)
    assert action_error.value.translation_key == "device_action_not_configured"
    assert action_error.value.translation_placeholders == {"device": DEVICE_NAME}
    mqtt_mock.async_publish.assert_not_called()


async def test_power_action_requires_device_for_multi_device_remote(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test multi-device remotes require a device through the activity field."""
    await _async_setup_remote(
        hass,
        mqtt_mock,
        device_registry,
        entity_registry,
        include_device_actions=True,
        include_second_device=True,
    )

    with pytest.raises(ServiceValidationError) as activity_error:
        await _async_call_power_action(hass, SERVICE_TURN_ON)
    assert activity_error.value.translation_key == "activity_required"
    mqtt_mock.async_publish.assert_not_called()


async def test_emitter_error_is_preserved(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test emitter transmission errors propagate without another transport."""
    await _async_setup_remote(
        hass,
        mqtt_mock,
        device_registry,
        entity_registry,
    )
    emitter_error = HomeAssistantError("send failed")

    with (
        patch(
            "custom_components.virtual_ir_remote.remote.infrared.async_send_command",
            new_callable=AsyncMock,
            side_effect=emitter_error,
        ),
        pytest.raises(HomeAssistantError) as raised_error,
    ):
        await _async_send_command(hass, "toggle_power")

    assert raised_error.value is emitter_error
    mqtt_mock.async_publish.assert_not_called()


async def test_registry_removal_makes_remote_unavailable(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Removing the emitter makes its Remote unavailable."""
    setup = await _async_setup_remote(hass, mqtt_mock, device_registry, entity_registry)
    entity_registry.async_remove(setup.emitter.entity_id)
    await hass.async_block_till_done()
    state = hass.states.get(REMOTE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert all(
        call.args[0] != EMITTER_TOPIC for call in mqtt_mock.async_publish.call_args_list
    )


async def test_send_command_validation_errors_are_atomic(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test input failures are validation errors and send no partial command list."""
    await _async_setup_remote(hass, mqtt_mock, device_registry, entity_registry)

    with pytest.raises(ServiceValidationError) as missing_device:
        await _async_send_command(hass, "toggle_power", include_device=False)
    assert missing_device.value.translation_key == "device_required"

    with pytest.raises(ServiceValidationError) as unknown_command:
        await _async_send_command(hass, ["toggle_power", "missing"])
    assert unknown_command.value.translation_key == "command_not_found"
    assert unknown_command.value.translation_placeholders == {
        "command": "missing",
        "device": DEVICE_NAME,
    }
    mqtt_mock.async_publish.assert_not_called()


async def test_invalid_stored_command_is_operational_error(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test invalid persisted command data is not reported as user input error."""
    await _async_setup_remote(
        hass,
        mqtt_mock,
        device_registry,
        entity_registry,
        command_bytes=(0x03,),
    )

    with pytest.raises(HomeAssistantError) as invalid_command:
        await _async_send_command(hass, "toggle_power")
    assert not isinstance(invalid_command.value, ServiceValidationError)
    assert invalid_command.value.translation_key == "invalid_command_configuration"
    mqtt_mock.async_publish.assert_not_called()


async def test_unavailable_emitter_is_operational_error(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no available transport raises a translated operational error."""
    setup = await _async_setup_remote(
        hass,
        mqtt_mock,
        device_registry,
        entity_registry,
    )
    hass.states.async_set(setup.emitter.entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    entity = hass.data[DATA_COMPONENT].get_entity(REMOTE_ENTITY_ID)
    assert isinstance(entity, VirtualIrRemote)

    with pytest.raises(HomeAssistantError) as unavailable:
        await entity.async_send_command(["toggle_power"], device=DEVICE_NAME)
    assert not isinstance(unavailable.value, ServiceValidationError)
    assert unavailable.value.translation_key == "blaster_unavailable"
    mqtt_mock.async_publish.assert_not_called()


async def test_multiple_commands_use_remote_default_delay(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test command lists follow the Remote building block's default delay."""
    await _async_setup_remote(
        hass,
        mqtt_mock,
        device_registry,
        entity_registry,
        include_second_command=True,
    )

    with patch(
        "custom_components.virtual_ir_remote.remote.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        await _async_send_command(hass, ["toggle_power", "toggle_speed"])

    assert mqtt_mock.async_publish.call_count == 2
    mock_sleep.assert_awaited_once_with(DEFAULT_DELAY_SECS)


async def test_repeats_apply_to_the_complete_command_sequence(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test repeats preserve the command sequence defined by Remote."""
    setup = await _async_setup_remote(
        hass,
        mqtt_mock,
        device_registry,
        entity_registry,
        include_second_command=True,
    )
    speed_command = NEC48Command(address=0x01, command=[0x07, 0x07])

    await _async_send_command(
        hass,
        ["toggle_power", "toggle_speed"],
        delay=0,
        repeats=2,
    )

    sent_timings = [
        json.loads(call.args[1])["timings"]
        for call in mqtt_mock.async_publish.mock_calls
    ]
    assert sent_timings == [
        setup.command.get_raw_timings(),
        speed_command.get_raw_timings(),
        setup.command.get_raw_timings(),
        speed_command.get_raw_timings(),
    ]
