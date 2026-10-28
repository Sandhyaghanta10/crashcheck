Workloads: 20 seeds x 6 puts. Crash injected after every op; all reachable disk images checked.

| Variant | Crash states | Corruption | Lost ack | Workloads w/ any bug |
|---|---:|---:|---:|---:|
| naive (no crc, no fsync) | 17320 | 8564 | 8604 | 20/20 |
| no-fsync (crc only) | 17320 | 0 | 17168 | 20/20 |
| no-crc (fsync every put) | 500 | 120 | 0 | 20/20 |
| ack-before-sync (crc, fsync every 2) | 800 | 0 | 480 | 20/20 |
| correct (crc + fsync every put) | 500 | 0 | 0 | 0/20 |

First counterexample per buggy variant:
- **naive (no crc, no fsync)** -> lost_ack: crash after op 1/6, recovered 0 of 6 puts
- **no-fsync (crc only)** -> lost_ack: crash after op 1/6, recovered 0 of 6 puts
- **no-crc (fsync every put)** -> corruption: crash after op 1/12, recovered 1 of 6 puts
- **ack-before-sync (crc, fsync every 2)** -> lost_ack: crash after op 1/9, recovered 0 of 6 puts
