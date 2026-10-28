"""Each buggy variant must be caught; the correct one must pass."""
import random

import pytest

from crashcheck.checker import CORRUPTION, LOST_ACK, explore, run_workload
from crashcheck.experiment import random_puts
from crashcheck.kvstore import VARIANTS, decode_log, encode

BY_PREFIX = {cfg.name.split(" ")[0]: cfg for cfg in VARIANTS}


def violations(cfg, seeds=10):
    total = {}
    for seed in range(seeds):
        rng = random.Random(seed)
        report = explore(cfg, run_workload(cfg, random_puts(rng, 5)), rng)
        for kind, n in report.violations.items():
            total[kind] = total.get(kind, 0) + n
    return total


def test_encode_decode_roundtrip():
    for cfg in VARIANTS:
        image = encode(cfg, b"k", b"v1") + encode(cfg, b"k", b"v2")
        assert decode_log(cfg, image) == [(b"k", b"v1"), (b"k", b"v2")]


def test_correct_variant_has_no_violations():
    assert violations(BY_PREFIX["correct"]) == {}


@pytest.mark.parametrize("name,expected", [
    ("naive", {CORRUPTION, LOST_ACK}),
    ("no-fsync", {LOST_ACK}),
    ("no-crc", {CORRUPTION}),
    ("ack-before-sync", {LOST_ACK}),
])
def test_buggy_variants_are_caught(name, expected):
    assert set(violations(BY_PREFIX[name])) == expected
