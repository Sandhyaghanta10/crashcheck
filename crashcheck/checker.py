"""Crash-consistency invariants for the KV store.

After ANY crash, recovery must yield a *prefix* of the puts that were issued
(no garbage, no gaps), and that prefix must include every put that was acked.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional

from .explorer import crash_images
from .kvstore import KV, KVStore, StoreConfig, decode_log
from .simdisk import Op, SimDisk

CORRUPTION = "corruption"  # recovered data was never written (torn/garbage record)
LOST_ACK = "lost_ack"      # a put we told the client succeeded is gone


@dataclass
class Run:
    """One workload execution: what was issued and where each ack happened."""
    issued: List[KV]
    ack_points: List[int]  # len(ops) right after put i returned
    ops: List[Op]


@dataclass
class Report:
    states: int = 0
    violations: Counter = field(default_factory=Counter)
    first_example: Optional[str] = None


def run_workload(cfg: StoreConfig, puts: List[KV]) -> Run:
    disk = SimDisk()
    store = KVStore(cfg, disk)
    ack_points = []
    for key, value in puts:
        store.put(key, value)
        ack_points.append(len(disk.ops))
    return Run(list(puts), ack_points, disk.ops)


def classify(cfg: StoreConfig, run: Run, crash_at: int, image: bytes) -> Optional[str]:
    recovered = decode_log(cfg, image)
    if recovered != run.issued[:len(recovered)]:
        return CORRUPTION
    acked = sum(1 for point in run.ack_points if point <= crash_at)
    if len(recovered) < acked:
        return LOST_ACK
    return None


def explore(cfg: StoreConfig, run: Run, rng: random.Random,
            max_states: int = 500) -> Report:
    """Crash after every op boundary and check every reachable disk image."""
    report = Report()
    for crash_at in range(len(run.ops) + 1):
        for image in crash_images(run.ops, crash_at, rng, max_states):
            report.states += 1
            kind = classify(cfg, run, crash_at, image)
            if kind:
                report.violations[kind] += 1
                if report.first_example is None:
                    report.first_example = (
                        f"{kind}: crash after op {crash_at}/{len(run.ops)}, "
                        f"recovered {len(decode_log(cfg, image))} of "
                        f"{len(run.issued)} puts")
    return report
