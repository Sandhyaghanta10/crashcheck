"""Run every store variant against random workloads and print a results table.

    python -m crashcheck.experiment --seeds 20 --puts 6
"""
from __future__ import annotations

import argparse
import random
import string
from collections import Counter
from pathlib import Path
from typing import List

from .checker import CORRUPTION, LOST_ACK, explore, run_workload
from .kvstore import KV, VARIANTS


def random_puts(rng: random.Random, count: int) -> List[KV]:
    """Few keys so overwrites happen; letters only so zero-fill is detectable."""
    keys = [b"a", b"b", b"c"]
    return [(rng.choice(keys),
             "".join(rng.choices(string.ascii_lowercase, k=rng.randint(4, 12))).encode())
            for _ in range(count)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--puts", type=int, default=6)
    parser.add_argument("--max-states", type=int, default=500)
    parser.add_argument("--out", type=Path, default=Path("results/results.md"))
    args = parser.parse_args()

    lines = [
        f"Workloads: {args.seeds} seeds x {args.puts} puts. "
        "Crash injected after every op; all reachable disk images checked.\n",
        "| Variant | Crash states | Corruption | Lost ack | Workloads w/ any bug |",
        "|---|---:|---:|---:|---:|",
    ]
    examples = []
    for cfg in VARIANTS:
        totals, states, buggy_runs = Counter(), 0, 0
        for seed in range(args.seeds):
            rng = random.Random(seed)
            run = run_workload(cfg, random_puts(rng, args.puts))
            report = explore(cfg, run, rng, args.max_states)
            states += report.states
            totals.update(report.violations)
            if report.violations:
                buggy_runs += 1
                if len(examples) < len(VARIANTS) and not any(cfg.name in e for e in examples):
                    examples.append(f"- **{cfg.name}** -> {report.first_example}")
        lines.append(f"| {cfg.name} | {states} | {totals[CORRUPTION]} | "
                     f"{totals[LOST_ACK]} | {buggy_runs}/{args.seeds} |")

    lines += ["", "First counterexample per buggy variant:", *examples]
    output = "\n".join(lines)
    print(output)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(output + "\n")


if __name__ == "__main__":
    main()
