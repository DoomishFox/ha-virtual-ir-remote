"""Tests for Virtual IR command protocols."""

import pytest
from custom_components.virtual_ir_remote.commands import NEC48Command
from custom_components.virtual_ir_remote.protocol import create_command
from infrared_protocols.commands import Command as InfraredCommand


def _decode_nec48_bytes(timings: list[int]) -> list[int]:
    """Decode data bytes from an NEC48 timing sequence."""
    values = []
    for start in range(2, 98, 16):
        value = 0
        for bit, timing_index in enumerate(range(start + 1, start + 16, 2)):
            if timings[timing_index] == -1687:
                value |= 1 << bit
        values.append(value)
    return values


def test_nec48_command() -> None:
    """Test NEC48 follows the infrared-protocols command contract."""
    command = NEC48Command(address=0x01, command=[0x03, 0x03])
    timings = command.get_raw_timings()

    assert isinstance(command, InfraredCommand)
    assert command.modulation == 38000
    assert command.repeat_count == 0
    assert len(timings) == 99
    assert timings[:6] == [9000, -4500, 562, -1687, 562, -562]
    assert _decode_nec48_bytes(timings) == [0x01, 0xFE, 0x03, 0xFC, 0x03, 0xFC]
    assert timings[-1] == 562


def test_nec48_command_repeats() -> None:
    """Test NEC48 repeat frames match the upstream NEC implementation."""
    timings = NEC48Command(
        address=0x01, command=[0x03, 0x03], repeat_count=2
    ).get_raw_timings()

    assert timings[-8:] == [
        -41000,
        9000,
        -2250,
        562,
        -96000,
        9000,
        -2250,
        562,
    ]


def test_protocol_factory() -> None:
    """Test a configured protocol creates its InfraredCommand type."""
    command = create_command("nec48", 0x01, [0x03, 0x03])

    assert isinstance(command, NEC48Command)


@pytest.mark.parametrize(
    ("address", "command"),
    [(0x100, [0x03, 0x03]), (0x01, [0x03]), (0x01, [0x03, 0x100])],
)
def test_nec48_rejects_invalid_bytes(address: int, command: list[int]) -> None:
    """Test NEC48 only accepts its 8-bit address and two-byte command."""
    with pytest.raises(ValueError):
        NEC48Command(address=address, command=command)


def test_protocol_factory_rejects_unknown_protocol() -> None:
    """Test the protocol factory rejects an unknown protocol."""
    with pytest.raises(ValueError, match="Unsupported IR protocol"):
        create_command("unknown", 0x01, [0x03, 0x03])
