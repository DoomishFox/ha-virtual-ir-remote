"""Remote entities for MQTT IR blasters."""

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.commands import Command as InfraredCommand

from homeassistant.components import infrared
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_PROTOCOL,
    STATE_UNAVAILABLE,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)

from .const import (
    ATTR_COMMANDS,
    CONF_COMMAND_ACTIONS,
    CONF_COMMAND_BYTES,
    CONF_COMMAND_NAME,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
    CommandAction,
)
from .protocol import create_command


@dataclass(frozen=True, slots=True)
class IrCommandConfig:
    """Configuration for a command assigned to a Remote."""

    protocol: str
    address: int
    command_bytes: tuple[int, ...]
    actions: frozenset[CommandAction]

    def create_command(self) -> InfraredCommand:
        """Create the command understood by the Infrared building block."""
        return create_command(self.protocol, self.address, self.command_bytes)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up configured virtual IR remotes."""
    commands: dict[tuple[str, str], IrCommandConfig] = {}
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_COMMAND):
        data = subentry.data
        commands[(data[CONF_DEVICE], data[CONF_COMMAND_NAME])] = IrCommandConfig(
            data[CONF_PROTOCOL],
            data[CONF_ADDRESS],
            tuple(data[CONF_COMMAND_BYTES]),
            frozenset(CommandAction(action) for action in data[CONF_COMMAND_ACTIONS]),
        )
    async_add_entities([VirtualIrRemote(entry, commands)])


class VirtualIrRemote(RemoteEntity):
    """A Remote entity backed by an MQTT infrared emitter."""

    _attr_has_entity_name = True
    _attr_is_on = True
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({ATTR_COMMANDS})

    def __init__(
        self,
        entry: ConfigEntry,
        commands: dict[tuple[str, str], IrCommandConfig],
    ) -> None:
        """Initialize the Remote."""
        self._commands = commands
        self._device_actions: dict[tuple[str, CommandAction], str] = {}
        for (device, command_name), command in commands.items():
            for action in command.actions:
                self._device_actions[(device, action)] = command_name
        self._action_devices = tuple(
            sorted({device for device, _ in self._device_actions})
        )
        self._attr_activity_list = list(self._action_devices)
        self._attr_supported_features = (
            RemoteEntityFeature.ACTIVITY
            if self._action_devices
            else RemoteEntityFeature(0)
        )
        self._infrared_entity_uuid: str = entry.data[CONF_INFRARED_ENTITY_ID]
        self._target_unsubscribes: list[CALLBACK_TYPE] = []
        self._attr_name = entry.title
        self._attr_unique_id = entry.entry_id

    @property
    @override
    def extra_state_attributes(self) -> dict[str, dict[str, list[str]]]:
        """Return the devices and commands configured for this Remote."""
        catalog: dict[str, list[str]] = defaultdict(list)
        for device, command in sorted(self._commands):
            catalog[device].append(command)
        return {ATTR_COMMANDS: dict(catalog)}

    @callback
    def _async_resolve_entity_id(self, entity_uuid: str) -> str | None:
        """Resolve a target registry UUID to its current entity ID."""
        if entry := er.async_get(self.hass).async_get(entity_uuid):
            return entry.entity_id
        return None

    @callback
    def _async_entity_available(self, entity_uuid: str) -> bool:
        """Return whether a configured emitter entity is available."""
        return self._async_available_entity_id(entity_uuid) is not None

    @callback
    def _async_available_entity_id(self, entity_uuid: str) -> str | None:
        """Resolve a emitter registry UUID when its entity is available."""
        entity_id = self._async_resolve_entity_id(entity_uuid)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state == STATE_UNAVAILABLE:
            return None
        return entity_id

    @callback
    def _async_update_availability(self) -> None:
        """Update availability from the MQTT emitter."""
        self._attr_available = self._async_entity_available(self._infrared_entity_uuid)

    @override
    async def async_added_to_hass(self) -> None:
        """Track availability and registry renames for the emitter."""
        await super().async_added_to_hass()
        self.async_on_remove(self._async_unsubscribe_targets)
        self._async_track_targets()

    @callback
    def _async_track_targets(self) -> None:
        """Track state and rename events for the configured emitter."""
        self._async_unsubscribe_targets()
        entity_id = self._async_resolve_entity_id(self._infrared_entity_uuid)
        entity_ids = {entity_id} if entity_id else set()
        if entity_ids:
            self._target_unsubscribes.append(
                async_track_state_change_event(
                    self.hass, entity_ids, self._async_target_state_changed
                )
            )
            self._target_unsubscribes.extend(
                async_track_entity_registry_updated_event(
                    self.hass, entity_id, self._async_target_registry_updated
                )
                for entity_id in entity_ids
            )
        self._async_update_availability()

    @callback
    def _async_unsubscribe_targets(self) -> None:
        """Stop tracking the emitter."""
        while self._target_unsubscribes:
            self._target_unsubscribes.pop()()

    @callback
    def _async_target_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Track the emitter after they are renamed or removed."""
        data = event.data
        if data["action"] == "update" and ATTR_ENTITY_ID not in data["changes"]:
            return
        if data["action"] not in ("remove", "update"):
            return
        self._async_track_targets()
        self.async_write_ha_state()

    @callback
    def _async_target_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Update availability when a emitter entity changes state."""
        available = self.available
        self._async_update_availability()
        if available != self.available:
            self.async_write_ha_state()

    async def _async_send_command(self, command: InfraredCommand) -> None:
        """Send through the configured MQTT infrared emitter."""
        if not self._async_entity_available(self._infrared_entity_uuid):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="blaster_unavailable",
            )
        await infrared.async_send_command(
            self.hass, self._infrared_entity_uuid, command, context=self._context
        )

    async def _async_send_device_action(
        self, action: CommandAction, kwargs: dict[str, Any]
    ) -> None:
        """Send the command assigned to a device power action."""
        device: str | None = kwargs.get(ATTR_ACTIVITY)
        if device is None:
            if len(self._action_devices) != 1:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="activity_required",
                )
            device = self._action_devices[0]

        if command_name := self._device_actions.get((device, action)):
            await self.async_send_command((command_name,), device=device)
            return
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_action_not_configured",
            translation_placeholders={"device": device},
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the configured turn-on command to a logical device."""
        await self._async_send_device_action(CommandAction.TURN_ON, kwargs)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the configured turn-off command to a logical device."""
        await self._async_send_device_action(CommandAction.TURN_OFF, kwargs)

    @override
    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send named commands through the selected MQTT IR blaster."""
        device = kwargs.get(ATTR_DEVICE)
        if device is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_required",
            )

        infrared_commands: list[InfraredCommand] = []
        for command_name in command:
            try:
                command_config = self._commands[(device, command_name)]
            except KeyError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="command_not_found",
                    translation_placeholders={
                        "command": command_name,
                        "device": device,
                    },
                ) from err
            try:
                infrared_commands.append(command_config.create_command())
            except ValueError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_command_configuration",
                    translation_placeholders={
                        "command": command_name,
                        "device": device,
                    },
                ) from err

        repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for repeat in range(repeats):
            for command_index, infrared_command in enumerate(infrared_commands):
                await self._async_send_command(infrared_command)
                if delay and (
                    command_index < len(infrared_commands) - 1 or repeat < repeats - 1
                ):
                    await asyncio.sleep(delay)
