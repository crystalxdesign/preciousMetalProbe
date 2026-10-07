#!/usr/bin/env python3
"""Request Pico LC captures, validate framing/CRC, append labelled JSONL."""
import argparse
import json
import struct
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path


def read_frame(port, timeout=15.0):
    deadline = time.monotonic() + timeout
    header = None
    samples = []
    while time.monotonic() < deadline:
        raw = port.readline()
        if not raw:
            continue
        try:
            line = raw.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("Non-ASCII serial data; reconnect and retry") from exc
        if line.startswith("ERROR "):
            raise ValueError(line)
        if line.startswith("FRAME "):
            if header is not None:
                raise ValueError("New frame before previous END")
            header = json.loads(line[6:])
            if header.get("protocol") != 1 or header.get("n") != 2048:
                raise ValueError("Unsupported protocol or sample count")
            if not 1 <= header.get("fs_hz", 0) <= 500000:
                raise ValueError("Invalid sampling rate")
        elif line.startswith("DATA "):
            if header is None:
                raise ValueError("DATA without FRAME")
            parts = [int(x) for x in line[5:].split(",")]
            if len(parts) < 2 or parts[0] != len(samples):
                raise ValueError("Missing/duplicate/out-of-order DATA")
            if any(not 0 <= x <= 65535 for x in parts[1:]):
                raise ValueError("Sample outside uint16 range")
            samples.extend(parts[1:])
            if len(samples) > header["n"]:
                raise ValueError("Too many samples")
        elif line.startswith("END "):
            if header is None or int(line[4:]) != header["id"]:
                raise ValueError("END frame ID mismatch")
            if len(samples) != header["n"]:
                raise ValueError("Incomplete frame")
            payload = struct.pack("<" + "H" * len(samples), *samples)
            if zlib.crc32(payload) != header["crc32"]:
                raise ValueError("CRC mismatch")
            if header.get("timeout") or header.get("fifo_over") or header.get("fifo_under"):
                raise ValueError("Firmware reports capture/DMA/FIFO failure")
            if not header.get("pulse_done"):
                raise ValueError("Excitation pulse did not complete")
            if header.get("adc_errors") or any(x & 0x8000 for x in samples):
                raise ValueError("ADC conversion error")
            if any(x & 0x7000 for x in samples):
                raise ValueError("Unexpected reserved ADC bits")
            if header.get("rail_samples") or any(x <= 16 or x >= 4079 for x in samples):
                raise ValueError("ADC near a rail; check waveform before collecting data")
            return header, samples
        # INFO/help/startup text is harmless and ignored.
    raise TimeoutError("No complete frame received within timeout")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", required=True, help="e.g. /dev/ttyACM0 or COM5")
    p.add_argument("--label", required=True, help="e.g. copper, aluminium, empty")
    p.add_argument("--specimen", required=True, help="Physical specimen ID; use none for empty")
    p.add_argument("--gap-mm", type=float, required=True)
    p.add_argument("--orientation", default="flat_parallel")
    p.add_argument("--cap-nf", type=float, default=47.0)
    p.add_argument("--coil-uh", type=float, default=470.0, help="Measured empty-coil value if known")
    p.add_argument("--session", default=None, help="Collection-session ID")
    p.add_argument("--notes", default="")
    p.add_argument("--count", type=int, default=100)
    p.add_argument("--interval", type=float, default=0.05, help="Minimum seconds between requests")
    p.add_argument("--output", type=Path, default=Path("data/captures.jsonl"))
    a = p.parse_args()
    if a.count < 1 or a.interval < 0 or a.gap_mm < 0 or a.cap_nf <= 0 or a.coil_uh <= 0:
        p.error("Count/capacitance/inductance must be positive; gap/interval nonnegative")
    import serial  # pyserial; imported here so protocol tests need no serial device
    a.output.parent.mkdir(parents=True, exist_ok=True)
    session = a.session or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with serial.Serial(a.port, 115200, timeout=0.25, write_timeout=5) as port:
        # USB CDC ignores baud rate. DTR asserted by pyserial enables stdio.
        time.sleep(1.0)
        port.reset_input_buffer()
        with a.output.open("a", encoding="utf-8") as out:
            for i in range(a.count):
                started = time.monotonic()
                port.write(b"c\n")
                port.flush()
                header, raw = read_frame(port)
                record = {
                    "capture_uuid": str(uuid.uuid4()),
                    "utc": datetime.now(timezone.utc).isoformat(),
                    "session": session, "label": a.label, "specimen": a.specimen,
                    "gap_mm": a.gap_mm, "orientation": a.orientation,
                    "cap_nf": a.cap_nf, "coil_uh": a.coil_uh, "notes": a.notes,
                    "firmware": header, "samples": raw,
                }
                out.write(json.dumps(record, separators=(",", ":")) + "\n")
                out.flush()  # completed records survive an interrupted run
                print(f"{i+1}/{a.count}: {a.label} specimen={a.specimen} frame={header['id']}")
                remaining = a.interval - (time.monotonic() - started)
                if remaining > 0:
                    time.sleep(remaining)
    print(f"Saved {a.count} validated captures to {a.output}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TimeoutError) as exc:
        raise SystemExit(f"Capture stopped: {exc}. Earlier completed records remain saved.")
