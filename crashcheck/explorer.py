"""Enumerate the on-disk images a crash at a given point could leave behind."""
from __future__ import annotations

import itertools
import random
from typing import Iterator, List, Sequence

from .simdisk import Fsync, Op, Write, apply_write

# For each un-fsynced write: 0 = never landed, 1 = torn, 2 = fully landed.
_CHOICES = (0, 1, 2)


def crash_images(ops: Sequence[Op], crash_at: int, rng: random.Random,
                 max_states: int) -> Iterator[bytes]:
    """Yield possible disk images if the machine dies after `ops[:crash_at]`.

    Everything up to the last fsync is durable. Writes after it are "pending"
    and may land in any combination. If 3^pending is too big we sample.
    """
    executed = ops[:crash_at]
    last_fsync = max((i for i, op in enumerate(executed) if isinstance(op, Fsync)),
                     default=-1)
    durable = bytearray()
    for op in executed[:last_fsync + 1]:
        if isinstance(op, Write):
            apply_write(durable, op)
    pending: List[Write] = [op for op in executed[last_fsync + 1:] if isinstance(op, Write)]

    if len(_CHOICES) ** len(pending) <= max_states:
        plans = itertools.product(_CHOICES, repeat=len(pending))
    else:
        plans = itertools.chain(
            [(0,) * len(pending), (2,) * len(pending)],
            (tuple(rng.choice(_CHOICES) for _ in pending) for _ in range(max_states)),
        )

    for plan in plans:
        image = bytearray(durable)
        for write, choice in zip(pending, plan):
            if choice == 1:
                apply_write(image, write.torn())
            elif choice == 2:
                apply_write(image, write)
        yield bytes(image)
