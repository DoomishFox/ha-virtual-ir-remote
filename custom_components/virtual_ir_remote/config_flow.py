"""Config flow for the Virtual IR Remote integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components import infrared
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ADDRESS, CONF_DEVICE, CONF_DEVICE_ID, CONF_PROTOCOL
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, selector

from .const import (
    CONF_COMMAND_ACTIONS,
    CONF_COMMAND_BYTES,
    CONF_COMMAND_NAME,
    CONF_INFRARED_ENTITY_ID,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    PROTOCOL_NEC48,
    SUBENTRY_TYPE_COMMAND,
    CommandAction,
)
from .discovery import async_find_emitter
from .protocol import PROTOCOLS, create_command

_NON_EMPTY_STRING = vol.All(str, vol.Strip, vol.Length(min=1))


def _parse_hex_byte(value: str) -> int:
    """Parse one user-provided hexadecimal byte."""
    try:
        parsed = int(value.strip(), 16)
    except ValueError as err:
        raise vol.Invalid("invalid hexadecimal byte") from err
    if not 0 <= parsed <= 0xFF:
        raise vol.Invalid("hexadecimal bytes must be between 00 and FF")
    return parsed


def _parse_hex_bytes(value: str) -> list[int]:
    """Parse a comma-separated hexadecimal byte array."""
    values = value.split(",")
    if not all(item.strip() for item in values):
        raise vol.Invalid("enter one or more comma-separated hexadecimal bytes")
    return [_parse_hex_byte(item) for item in values]


class VirtualIrRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Virtual IR Remote."""

    VERSION = CONFIG_ENTRY_VERSION

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_COMMAND: CommandSubentryFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the blaster for a new Remote."""
        return await self._async_remote_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the selected blaster."""
        return await self._async_remote_step("reconfigure", user_input)

    async def _async_remote_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Validate the blaster and store its registry identifiers."""
        entry = self._get_reconfigure_entry() if step_id == "reconfigure" else None
        errors: dict[str, str] = {}
        suggested_values = user_input
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = dr.async_get(self.hass).async_get(device_id)
            emitter = async_find_emitter(self.hass, device_id)
            if device is None or emitter is None:
                errors["base"] = "unsupported_device"
            elif any(
                configured.entry_id != (entry.entry_id if entry else None)
                and configured.data[CONF_DEVICE_ID] == device_id
                for configured in self._async_current_entries()
            ):
                errors["base"] = "already_configured"
            else:
                await self.async_set_unique_id(device_id)
                data = {
                    CONF_DEVICE_ID: device_id,
                    CONF_INFRARED_ENTITY_ID: emitter.id,
                }
                if entry is not None:
                    return self.async_update_and_abort(
                        entry,
                        unique_id=device_id,
                        data=data,
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.name_by_user or device.name or "Virtual IR Remote",
                    data=data,
                )
        elif entry is not None:
            suggested_values = {
                CONF_DEVICE_ID: entry.data[CONF_DEVICE_ID],
            }
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                self._schema(), suggested_values
            ),
            errors=errors,
        )

    @staticmethod
    def _schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): selector.DeviceSelector(
                    selector.DeviceSelectorConfig(
                        entity=selector.EntityFilterSelectorConfig(
                            domain=infrared.DOMAIN,
                            device_class=infrared.InfraredDeviceClass.EMITTER,
                            integration=MQTT_DOMAIN,
                        )
                    )
                ),
            }
        )


class CommandSubentryFlowHandler(ConfigSubentryFlow):
    """Add or reconfigure a named IR command."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a command."""
        if user_input is not None:
            errors, data = self._async_validate_command(user_input)
            if data is not None:
                return self.async_create_entry(
                    title=self._command_title(data), data=data
                )
        else:
            errors = {}
        return self._async_show_command_form("user", user_input, errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure a command."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            errors, data = self._async_validate_command(
                user_input, current_subentry_id=subentry.subentry_id
            )
            if data is not None:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=self._command_title(data),
                    data=data,
                )
            suggested_values = user_input
        else:
            errors = {}
            suggested_values = self._suggested_values(subentry)
        return self._async_show_command_form("reconfigure", suggested_values, errors)

    @callback
    def _async_validate_command(
        self,
        user_input: dict[str, Any],
        *,
        current_subentry_id: str | None = None,
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Validate a named command."""
        entry = self._get_entry()
        errors: dict[str, str] = {}
        try:
            data = self._validated_data(user_input)
        except ValueError, vol.Invalid:
            errors["base"] = "invalid_command"
        else:
            command_actions = set(data[CONF_COMMAND_ACTIONS])
            if any(
                subentry.subentry_id != current_subentry_id
                and subentry.data[CONF_DEVICE] == data[CONF_DEVICE]
                and (
                    subentry.data[CONF_COMMAND_NAME] == data[CONF_COMMAND_NAME]
                    or bool(
                        command_actions.intersection(
                            subentry.data[CONF_COMMAND_ACTIONS]
                        )
                    )
                )
                for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_COMMAND)
            ):
                errors["base"] = "already_configured"
            else:
                return {}, data
        return errors, None

    @callback
    def _async_show_command_form(
        self,
        step_id: str,
        suggested_values: dict[str, Any] | None,
        errors: dict[str, str],
    ) -> SubentryFlowResult:
        """Show the command form."""
        schema = self._schema()
        if suggested_values is not None:
            schema = self.add_suggested_values_to_schema(schema, suggested_values)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={"remote": self._get_entry().title},
        )

    def _command_title(self, data: dict[str, Any]) -> str:
        """Return a descriptive command subentry title."""
        return f"{data[CONF_DEVICE]} — {data[CONF_COMMAND_NAME]}"

    @staticmethod
    def _schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_DEVICE): _NON_EMPTY_STRING,
                vol.Required(CONF_COMMAND_NAME): _NON_EMPTY_STRING,
                vol.Required(CONF_COMMAND_ACTIONS, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[action.value for action in CommandAction],
                        multiple=True,
                        translation_key="command_actions",
                    )
                ),
                vol.Required(CONF_PROTOCOL, default=PROTOCOL_NEC48): (
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(PROTOCOLS), translation_key="protocol"
                        )
                    )
                ),
                vol.Required(CONF_ADDRESS): str,
                vol.Required(CONF_COMMAND_BYTES): str,
            }
        )

    @staticmethod
    def _validated_data(user_input: dict[str, Any]) -> dict[str, Any]:
        selected_actions = {
            CommandAction(action) for action in user_input[CONF_COMMAND_ACTIONS]
        }
        command_actions = [
            action.value for action in CommandAction if action in selected_actions
        ]
        address = _parse_hex_byte(user_input[CONF_ADDRESS])
        command_bytes = _parse_hex_bytes(user_input[CONF_COMMAND_BYTES])
        create_command(user_input[CONF_PROTOCOL], address, command_bytes)
        return {
            **user_input,
            CONF_ADDRESS: address,
            CONF_COMMAND_BYTES: command_bytes,
            CONF_COMMAND_ACTIONS: command_actions,
        }

    @staticmethod
    def _suggested_values(subentry: ConfigSubentry) -> dict[str, Any]:
        return {
            **subentry.data,
            CONF_COMMAND_ACTIONS: subentry.data[CONF_COMMAND_ACTIONS],
            CONF_ADDRESS: f"{subentry.data[CONF_ADDRESS]:02X}",
            CONF_COMMAND_BYTES: ", ".join(
                f"{value:02X}" for value in subentry.data[CONF_COMMAND_BYTES]
            ),
        }
