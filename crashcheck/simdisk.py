"""A simulated disk that records every write and fsync so crashes can be replayed.

Model (deliberately simple, same spirit as ALICE / CrashMonkey):
  * Writes are only guaranteed durable once a later fsync returns.
  * Un-fsynced writes may reach the disk in ANY subset, in ANY order.
  * A single un-fsynced write may be "torn": the file grew but only part of the
    data landed; the rest reads back as zeros.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Union


@dataclass(frozen=True)
class Write:
    offset: int
    data: bytes

    def torn(self) -> "Write":
        """First half is real data, second half never made it (zeros)."""
        half = len(self.data) // 2
        return Write(self.offset, self.data[:half] + bytes(len(self.data) - half))


@dataclass(frozen=True)
class Fsync:
    pass


Op = Union[Write, Fsync]


class SimDisk:
    """Append-only operation log. The store talks to this instead of a real file."""

    def __init__(self) -> None:
        self.ops: List[Op] = []

    def write(self, offset: int, data: bytes) -> None:
        self.ops.append(Write(offset, data))

    def fsync(self) -> None:
        self.ops.append(Fsync())


def apply_write(image: bytearray, write: Write) -> None:
    """Apply a write to an in-memory file image, zero-filling any hole."""
    end = write.offset + len(write.data)
    if len(image) < end:
        image.extend(bytes(end - len(image)))
    image[write.offset:end] = write.data
