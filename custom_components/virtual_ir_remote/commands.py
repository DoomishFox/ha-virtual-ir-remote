"""Infrared command types for Virtual IR Remote."""

from collections.abc import Sequence
from typing import override

from infrared_protocols.commands import Command as InfraredCommand
from infrared_protocols.commands.nec import (
    BIT_HIGH,
    FRAME_GAP,
    INITIAL_FRAME_GAP,
    LEADER_HIGH,
    LEADER_LOW,
    ONE_LOW,
    REPEAT_LOW,
    ZERO_LOW,
)


class NEC48Command(InfraredCommand):
    """NEC-style command containing two independently checksummed command bytes."""

    address: int
    command: tuple[int, int]

    def __init__(
        self,
        *,
        address: int,
        command: Sequence[int],
        modulation: int = 38000,
        repeat_count: int = 0,
    ) -> None:
        """Initialize an NEC48 command."""
        super().__init__(modulation=modulation, repeat_count=repeat_count)
        if not 0 <= address <= 0xFF:
            raise ValueError(
                f"address must be an 8-bit value (0-0xFF), got {address:#x}"
            )
        if len(command) != 2 or any(not 0 <= value <= 0xFF for value in command):
            raise ValueError("command must contain exactly two 8-bit values")
        self.address = address
        self.command = (command[0], command[1])

    @override
    def get_raw_timings(self) -> list[int]:
        """Get raw NEC48 timings with positive pulses and negative spaces."""
        timings = [LEADER_HIGH, -LEADER_LOW]
        values = (
            self.address,
            self.address ^ 0xFF,
            self.command[0],
            self.command[0] ^ 0xFF,
            self.command[1],
            self.command[1] ^ 0xFF,
        )
        for value in values:
            for bit in range(8):
                timings.extend(
                    (BIT_HIGH, -ONE_LOW)
                    if value & (1 << bit)
                    else (BIT_HIGH, -ZERO_LOW)
                )
        timings.append(BIT_HIGH)

        gap = INITIAL_FRAME_GAP
        for _ in range(self.repeat_count):
            timings.extend((-gap, LEADER_HIGH, -REPEAT_LOW, BIT_HIGH))
            gap = FRAME_GAP

        return timings
