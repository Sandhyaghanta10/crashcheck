# crashcheck — crash-consistency testing for a toy write-ahead-log KV store

A small research-style study: **which design decisions in an append-only WAL key-value
store are actually necessary for crash safety, and can a systematic crash explorer
find the bugs when they're missing?**

Inspired by ALICE (*All File Systems Are Not Created Equal*, OSDI '14) and
CrashMonkey. This is a learning/research prototype, not a reimplementation of those tools.

## Research question & hypothesis
- **Q:** If we crash after *every* operation and consider *every* way un-fsynced writes could
  land on disk, which store designs violate their guarantees?
- **H:** Both a per-record checksum (detects torn writes) and fsync-before-ack (durability)
  are *independently necessary*; removing either causes a distinct, detectable failure class.

## Method
1. `SimDisk` records every `write` / `fsync` instead of touching a real disk.
2. `explorer.py` crashes after each op boundary. Everything before the last fsync is durable.
   Each later (pending) write may be **absent, torn (half data, half zeros), or fully landed**,
   in any combination. If 3^pending exceeds a cap we randomly sample.
3. `checker.py` verifies one invariant after recovery: *the recovered log is a prefix of the
   issued puts and includes every acked put.* Violations are classified as
   **corruption** (garbage/torn data surfaced) or **lost ack** (acknowledged write vanished).
4. Five store variants (`kvstore.py`) differ only in two knobs: checksum on/off, fsync cadence.

## Results (20 random workloads x 6 puts each)

| Variant | Crash states | Corruption | Lost ack | Workloads w/ any bug |
|---|---:|---:|---:|---:|
| naive (no crc, no fsync) | 17320 | 8564 | 8604 | 20/20 |
| no-fsync (crc only) | 17320 | 0 | 17168 | 20/20 |
| no-crc (fsync every put) | 500 | 120 | 0 | 20/20 |
| ack-before-sync (crc, fsync every 2) | 800 | 0 | 480 | 20/20 |
| correct (crc + fsync every put) | 500 | 0 | 0 | 0/20 |

**Findings**
- Checksums and fsync fix *different* failure classes: dropping the CRC yields only corruption;
  dropping fsync yields only lost acks. Hypothesis supported (within this model).
- "Fsync every N>1 but ack immediately" is subtle: it looks safe but loses acked data. This is
  the group-commit pitfall; acks must wait for the covering fsync.

## Threats to validity / limitations (honest list)
- Single file, append-only, fixed crash model (absent/torn/full). Real filesystems add
  directory entries, rename atomicity, metadata journaling, and sector-level tearing.
- Torn writes are modeled as half-data/half-zeros only.
- When the pending set is large we *sample* states, so counts for those rows are lower bounds.
- Numbers are about this simulator, not any real filesystem.

## Future work
- Add log compaction via write-temp-then-rename and look for the classic missing directory-fsync bug.
- Make the crash model configurable per filesystem (ext4 ordered vs. data=writeback).
- Compare against LSM-style designs (e.g. WiscKey's value log).

## Reproduce
```bash
uv venv && uv pip install pytest
.venv/bin/python -m pytest -q
.venv/bin/python -m crashcheck.experiment --seeds 20 --puts 6   # writes results/results.md
```
