"""Registry of configurable infrared command protocols."""

from collections.abc import Sequence
from typing import Final, Protocol

from infrared_protocols.commands import Command as InfraredCommand

from .commands import NEC48Command
from .const import PROTOCOL_NEC48


class CommandFactory(Protocol):
    """Create a command from the integration's configurable byte fields."""

    def __call__(self, *, address: int, command: Sequence[int]) -> InfraredCommand:
        """Create a command."""


def _create_nec48_command(*, address: int, command: Sequence[int]) -> InfraredCommand:
    return NEC48Command(address=address, command=command)


PROTOCOLS: Final[dict[str, CommandFactory]] = {PROTOCOL_NEC48: _create_nec48_command}


def create_command(
    protocol: str, address: int, command: Sequence[int]
) -> InfraredCommand:
    """Create an InfraredCommand for a configured protocol."""
    try:
        factory = PROTOCOLS[protocol]
    except KeyError as err:
        raise ValueError(f"Unsupported IR protocol: {protocol}") from err
    return factory(address=address, command=command)
