"""Protocol integrity tests using an in-memory serial stream."""
import io
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from capture import read_frame


def frame(values=None, **updates):
    values = values or [2048] * 2048
    h = dict(protocol=1, id=1, n=2048, fs_hz=500000, timeout=0, fifo_over=0,
             fifo_under=0, pulse_done=1, adc_errors=0, rail_samples=0,
             crc32=zlib.crc32(struct.pack("<2048H", *values)))
    h.update(updates)
    lines = ["FRAME " + json.dumps(h)]
    for start in range(0, 2048, 32):
        lines.append("DATA " + str(start) + "," + ",".join(map(str, values[start:start+32])))
    lines.append("END 1")
    return ("\n".join(lines) + "\n").encode()


class ProtocolTests(unittest.TestCase):
    def test_valid(self):
        h, values = read_frame(io.BytesIO(frame()))
        self.assertEqual(len(values), 2048)
        self.assertEqual(h["fs_hz"], 500000)

    def test_crc_corruption(self):
        with self.assertRaisesRegex(ValueError, "CRC"):
            read_frame(io.BytesIO(frame().replace(b"DATA 0,2048", b"DATA 0,2049")))

    def test_missing_chunk(self):
        data = frame().splitlines(keepends=True)
        del data[2]
        with self.assertRaisesRegex(ValueError, "order"):
            read_frame(io.BytesIO(b"".join(data)))

    def test_reported_faults(self):
        for flag in ["timeout", "fifo_over", "fifo_under", "adc_errors", "rail_samples"]:
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                read_frame(io.BytesIO(frame(**{flag: 1})))

    def test_adc_err_bit(self):
        values = [2048] * 2048
        values[100] |= 0x8000
        with self.assertRaisesRegex(ValueError, "conversion"):
            read_frame(io.BytesIO(frame(values)))

    def test_rail_value_even_if_header_misses_it(self):
        values = [2048] * 2048
        values[100] = 4095
        with self.assertRaisesRegex(ValueError, "rail"):
            read_frame(io.BytesIO(frame(values)))

    def test_wrong_end_id(self):
        with self.assertRaisesRegex(ValueError, "ID"):
            read_frame(io.BytesIO(frame().replace(b"END 1", b"END 2")))


if __name__ == "__main__":
    unittest.main()
