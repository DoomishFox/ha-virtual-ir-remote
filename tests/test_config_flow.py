"""Tests for the Virtual IR Remote config flow."""

import pytest
from custom_components.virtual_ir_remote.const import (
    CONF_COMMAND_ACTIONS,
    CONF_COMMAND_BYTES,
    CONF_COMMAND_NAME,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
    CommandAction,
)
from homeassistant import config_entries
from homeassistant.components import infrared
from homeassistant.components.infrared import InfraredDeviceClass
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_DEVICE, CONF_DEVICE_ID, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _add_ir_blaster(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> tuple[dr.DeviceEntry, er.RegistryEntry]:
    """Add a Zigbee2MQTT IR blaster to the registries."""
    mqtt_entry = MockConfigEntry(domain=MQTT_DOMAIN)
    mqtt_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mqtt_entry.entry_id,
        identifiers={(MQTT_DOMAIN, "zigbee2mqtt_blaster")},
        manufacturer="Moes",
        model="Universal smart IR remote control",
        model_id="UFO-R11",
        name="Bedroom IR Sender",
    )
    emitter = entity_registry.async_get_or_create(
        infrared.DOMAIN,
        MQTT_DOMAIN,
        "blaster_ir_emitter_zigbee2mqtt",
        config_entry=mqtt_entry,
        device_id=device.id,
        original_device_class=InfraredDeviceClass.EMITTER,
        original_name="Ir emitter",
    )
    return device, emitter


@pytest.mark.usefixtures("mock_setup_entry")
async def test_remote_setup_and_reconfigure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Create one Remote per blaster, then reconfigure it."""
    device, emitter = _add_ir_blaster(hass, device_registry, entity_registry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: device.id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.title == "Bedroom IR Sender"
    assert entry.unique_id == device.id
    assert entry.data == {
        CONF_DEVICE_ID: device.id,
        CONF_INFRARED_ENTITY_ID: emitter.id,
    }
    assert set(entry.supported_subentry_types) == {SUBENTRY_TYPE_COMMAND}

    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    duplicate = await hass.config_entries.flow.async_configure(
        duplicate["flow_id"], {CONF_DEVICE_ID: device.id}
    )
    assert duplicate["errors"] == {"base": "already_configured"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: device.id}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Bedroom IR Sender"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_rejects_blaster_owned_by_another_remote(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Reconfiguration cannot create a second Remote for an occupied blaster."""
    device, _ = _add_ir_blaster(hass, device_registry, entity_registry)
    _entry(hass, device.id, "Bedroom")
    other = _entry(hass, "other-device", "Office")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": other.entry_id,
        },
        data={CONF_DEVICE_ID: device.id},
    )
    assert result["errors"] == {"base": "already_configured"}
    assert other.data[CONF_DEVICE_ID] == "other-device"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_remote_rejects_unsupported_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Require an enabled MQTT emitter."""
    device, emitter = _add_ir_blaster(hass, device_registry, entity_registry)
    entity_registry.async_update_entity(
        emitter.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_DEVICE_ID: device.id},
    )
    assert result["errors"] == {"base": "unsupported_device"}


def _entry(hass: HomeAssistant, device_id: str, title: str) -> MockConfigEntry:
    """Create a Remote with its own command namespace."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=device_id,
        data={
            CONF_DEVICE_ID: device_id,
            CONF_INFRARED_ENTITY_ID: "emitter-id",
        },
    )
    entry.add_to_hass(hass)
    return entry


COMMAND_INPUT = {
    CONF_DEVICE: "Fan",
    CONF_COMMAND_NAME: "power",
    CONF_COMMAND_ACTIONS: [CommandAction.TURN_ON],
    CONF_PROTOCOL: "nec48",
    CONF_ADDRESS: "01",
    CONF_COMMAND_BYTES: "03, 03",
}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_commands_are_scoped_to_remote(hass: HomeAssistant) -> None:
    """The same virtual device and command can exist on independent remotes."""
    for device_id, title in (
        ("bedroom-device", "Bedroom"),
        ("office-device", "Office"),
    ):
        entry = _entry(hass, device_id, title)
        assert await hass.config_entries.async_setup(entry.entry_id)
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_COMMAND),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["description_placeholders"] == {"remote": entry.title}
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], COMMAND_INPUT
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        command = next(iter(entry.subentries.values()))
        assert command.title == "Fan — power"
        assert command.data[CONF_COMMAND_BYTES] == [3, 3]
        assert "remote_id" not in command.data


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({}, id="duplicate-name"),
        pytest.param({CONF_COMMAND_NAME: "other-power"}, id="duplicate-action"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_commands(
    hass: HomeAssistant,
    changes: dict[str, str],
) -> None:
    """Names and power assignments must be unambiguous within a virtual device."""
    entry = _entry(hass, "device", "Bedroom")
    assert await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": config_entries.SOURCE_USER},
        data=COMMAND_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": config_entries.SOURCE_USER},
        data=COMMAND_INPUT | changes,
    )
    assert result["errors"] == {"base": "already_configured"}


@pytest.mark.parametrize("value", ["03", "GG, 03", "100, 03", "03,"])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_invalid_command(hass: HomeAssistant, value: str) -> None:
    """Invalid hexadecimal or protocol input stays in the form."""
    entry = _entry(hass, "device", "Bedroom")
    assert await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": config_entries.SOURCE_USER},
        data=COMMAND_INPUT | {CONF_COMMAND_BYTES: value},
    )
    assert result["errors"] == {"base": "invalid_command"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_command(hass: HomeAssistant) -> None:
    """Changing a command preserves parent ownership and updates its display name."""
    entry = _entry(hass, "device", "Bedroom")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": config_entries.SOURCE_USER},
        data=COMMAND_INPUT,
    )
    command = next(iter(entry.subentries.values()))
    reconfigure_result = await entry.start_subentry_reconfigure_flow(
        hass, command.subentry_id
    )
    assert reconfigure_result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        reconfigure_result["flow_id"],
        COMMAND_INPUT
        | {
            CONF_DEVICE: "TV",
            CONF_COMMAND_ACTIONS: [CommandAction.TURN_OFF, CommandAction.TURN_ON],
        },
    )
    assert result["reason"] == "reconfigure_successful"
    updated = entry.subentries[command.subentry_id]
    assert updated.title == "TV — power"
    assert updated.data[CONF_COMMAND_ACTIONS] == [
        CommandAction.TURN_ON,
        CommandAction.TURN_OFF,
    ]
