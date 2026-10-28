"""A tiny append-only write-ahead-log KV store, with two knobs that matter.

Instead of five near-identical classes, one `StoreConfig` captures the design
decisions we want to compare:
  * checksum    - does each record carry a CRC32 so torn records are detectable?
  * fsync_every - fsync after every N puts (0 = never). `put` returns ("acks")
                  right after, whether or not an fsync happened.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import List, Tuple

from .simdisk import SimDisk

KV = Tuple[bytes, bytes]


@dataclass(frozen=True)
class StoreConfig:
    name: str
    checksum: bool
    fsync_every: int  # 0 = never fsync


VARIANTS = [
    StoreConfig("naive (no crc, no fsync)", checksum=False, fsync_every=0),
    StoreConfig("no-fsync (crc only)", checksum=True, fsync_every=0),
    StoreConfig("no-crc (fsync every put)", checksum=False, fsync_every=1),
    StoreConfig("ack-before-sync (crc, fsync every 2)", checksum=True, fsync_every=2),
    StoreConfig("correct (crc + fsync every put)", checksum=True, fsync_every=1),
]


def encode(cfg: StoreConfig, key: bytes, value: bytes) -> bytes:
    """Record = [len u32][crc u32 if enabled][klen u16][key][value]."""
    payload = struct.pack("<H", len(key)) + key + value
    header = struct.pack("<I", len(payload))
    if cfg.checksum:
        header += struct.pack("<I", zlib.crc32(payload))
    return header + payload


def decode_log(cfg: StoreConfig, image: bytes) -> List[KV]:
    """Recovery: replay records until the first one that looks invalid."""
    header_size = 8 if cfg.checksum else 4
    records: List[KV] = []
    pos = 0
    while pos + header_size <= len(image):
        (length,) = struct.unpack_from("<I", image, pos)
        start = pos + header_size
        if length < 2 or start + length > len(image):
            break
        payload = image[start:start + length]
        if cfg.checksum:
            (crc,) = struct.unpack_from("<I", image, pos + 4)
            if zlib.crc32(payload) != crc:
                break
        (klen,) = struct.unpack_from("<H", payload)
        if 2 + klen > length:
            break
        records.append((payload[2:2 + klen], payload[2 + klen:]))
        pos = start + length
    return records


class KVStore:
    def __init__(self, cfg: StoreConfig, disk: SimDisk) -> None:
        self.cfg, self.disk = cfg, disk
        self._offset = 0
        self._puts = 0

    def put(self, key: bytes, value: bytes) -> None:
        record = encode(self.cfg, key, value)
        self.disk.write(self._offset, record)
        self._offset += len(record)
        self._puts += 1
        if self.cfg.fsync_every and self._puts % self.cfg.fsync_every == 0:
            self.disk.fsync()
