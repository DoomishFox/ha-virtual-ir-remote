"""Constants for the Virtual IR Remote integration."""

from enum import StrEnum
from typing import Final

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON

DOMAIN: Final = "virtual_ir_remote"
CONFIG_ENTRY_VERSION: Final = 1
CONF_COMMAND_BYTES: Final = "command_bytes"
CONF_COMMAND_ACTIONS: Final = "command_actions"
CONF_COMMAND_NAME: Final = "command_name"
CONF_INFRARED_ENTITY_ID: Final = "infrared_entity_id"
ATTR_COMMANDS: Final = "commands"
PROTOCOL_NEC48: Final = "nec48"
SUBENTRY_TYPE_COMMAND: Final = "command"


class CommandAction(StrEnum):
    """Standard Remote actions that can use a configured command."""

    TURN_ON = SERVICE_TURN_ON
    TURN_OFF = SERVICE_TURN_OFF
