#!/usr/bin/env python3
"""Inspect one JSONL waveform; baseline-subtracted ADC counts, not calibrated volts."""
import argparse
import json
import numpy as np
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument("--index", type=int, default=0)
    p.add_argument("--save", help="PNG/SVG filename; omit to open interactive plot")
    a = p.parse_args()
    if a.index < 0:
        p.error("index must be nonnegative")
    with open(a.input, encoding="utf-8") as f:
        record = next((json.loads(line) for i, line in enumerate(f) if i == a.index), None)
    if record is None:
        p.error("index exceeds number of records")
    h = record["firmware"]
    y = np.asarray(record["samples"], dtype=float)
    # First conversion completes about one conversion period after ADC launch.
    t = (np.arange(len(y)) + 1) * 1e6 / h["fs_hz"]
    baseline_n = max(8, min(32, int(h["rise_us_est"] * h["fs_hz"] / 1e6) - 8))
    y -= np.median(y[:baseline_n])
    plt.figure(figsize=(11, 4))
    plt.plot(t, y, lw=1)
    plt.axvspan(h["rise_us_est"], h["fall_us_est"], alpha=.25, color="orange",
                label="Estimated excitation interval")
    plt.xlabel("Time since ADC start (µs; nominal conversion-completion axis)")
    plt.ylabel("ADC counts relative to baseline")
    plt.title(f"{record['label']} • specimen {record['specimen']} • gap {record['gap_mm']} mm")
    plt.grid(alpha=.25)
    plt.legend()
    plt.tight_layout()
    if a.save:
        plt.savefig(a.save, dpi=160)
    else:
        plt.show()


if __name__ == "__main__":
    main()
