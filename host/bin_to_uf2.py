#!/usr/bin/env python3
"""Convert an RP2040 flash-image BIN at 0x10000000 to standard UF2 blocks."""
import argparse
from pathlib import Path
import struct


def convert(data):
    if not data or len(data) > 2 * 1024 * 1024:
        raise ValueError("Expected a nonempty flash image fitting the Pico's 2 MiB flash")
    count = (len(data) + 255) // 256
    blocks = []
    for i in range(count):
        payload = data[i * 256:(i + 1) * 256].ljust(256, b"\x00")
        header = struct.pack("<8I", 0x0A324655, 0x9E5D5157, 0x2000,
                             0x10000000 + i * 256, 256, i, count, 0xE48BFF56)
        blocks.append(header + payload + bytes(476 - 256) + struct.pack("<I", 0x0AB16F30))
    return b"".join(blocks)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    a.output.write_bytes(convert(a.input.read_bytes()))
    print(f"Created RP2040 UF2: {a.output}")
