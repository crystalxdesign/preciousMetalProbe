# Pico LC metal-sample capture

A complete **Pico SDK C project for the original RP2040 Raspberry Pi Pico**,
plus a labelled USB data logger and a custom electrical wiring diagram.
This collects training data; it does not yet train or run a classifier.

## Files

- `firmware/main.c`: ADC FIFO, 16-bit DMA capture, hardware ADC stop, USB commands.
- `firmware/excite.pio`: deterministic 5 µs active-high excitation pulse.
- `firmware/CMakeLists.txt`: Pico SDK build.
- `host/capture.py`: validates records and appends labelled JSONL training data.
- `host/plot_capture.py`: inspect a captured waveform.
- `docs/preciousMetalProbe.png` and `.svg`: wiring schematic with component pin numbers.
- `docs/wiring.md`: complete net list, component list and bring-up procedure.
- `tests/test_protocol.py`: serial framing, CRC and fault-rejection tests.

## Circuit

Use the circuit in `docs/preciousMetalProbe.png`. GP15 controls the active-high
TMUX1101 switch; the switch connects +3.3 V through 330 Ω to TANK for 5 µs.
A 470 µH air-core sensing coil and 47 nF capacitor are in parallel between TANK
and buffered BIAS (~1.65 V). A second OPA2320 buffer feeds GP26 / ADC0 through
100 Ω, with 4.7 nF to AGND at the ADC pin. All analogue ICs use the Pico's 3.3 V
supply. GP15 has an external 100 kΩ pulldown to keep excitation off at reset.

Verify the waveform with an oscilloscope before connecting GP26. Both TANK and
ADC should remain comfortably within 0.3–3.0 V. The amplifier and switch inputs
must also stay within their operating ranges. If ringing is excessive, shorten
the pulse (changing the PIO delay and PULSE_US together) or increase R3.
The ADC RC network is not a strong anti-alias filter. Exclude switching
transients from fitting, and investigate any substantial high-frequency pickup.

## Capture behaviour and timing

- ADC0 only; no round-robin sampling. 500 kS/s at the default 48 MHz ADC clock.
- 2048 raw uint16 samples, retaining 12 data bits and error bit 15.
- Nominal record length: 4.096 ms; sample interval: 2 µs.
- Approximately 128 µs of pre-pulse baseline; the actual rise is a little later
  because ADC start and PIO enable are sequential CPU operations.
- PIO runs at 1 MHz and generates a 5 µs high interval, followed by low.
- A chained DMA write stops the ADC when the capture buffer is full.
- USB transmission occurs after sampling. No unsolicited captures at boot.
- At least 20 ms settling time precedes each requested capture.

**ADC/PIO alignment is estimated, not exact sample synchronisation.** They use
different clocks. `rise_us_est` and `fall_us_est` are relative to software ADC
start, using bracketed launch times and the PIO delay. `launch_bracket_us`
measures those software brackets; it is not a total timing-uncertainty bound.
Allow a few microseconds for divider phase, peripheral launch and ADC aperture.
For model inputs, find/refine the pulse boundary in the waveform and crop a
consistent post-pulse interval. Do not treat the header as an exact trigger index.

The plot uses nominal conversion-completion times `(index + 1) / fs`.
For voltage conversion use the measured ADC reference:
`V_TANK ≈ raw * VREF / 4096`. Subtract pre-pulse baseline to estimate the voltage
across the LC circuit. Raw counts are preserved; the RP2040's nominal 12-bit ADC
does not imply 12-bit effective accuracy or perfect linearity.

## Build from source

Install CMake, an Arm embedded GCC toolchain, Python 3, Git and a native C/C++
compiler. On Debian/Ubuntu a usual starting command is:

```sh
sudo apt install cmake build-essential gcc-arm-none-eabi libnewlib-arm-none-eabi git python3 python3-venv
git clone --branch 2.2.0 --depth 1 https://github.com/raspberrypi/pico-sdk.git
git -C pico-sdk submodule update --init lib/tinyusb
export PICO_SDK_PATH="$PWD/pico-sdk"
```

From the extracted `lc_metal_capture` directory:

```sh
cmake -S firmware -B build -DPICO_BOARD=pico -DCMAKE_BUILD_TYPE=Release -DPICO_NO_PICOTOOL=1
cmake --build build -j4
```

The tested command above builds ELF/BIN and uses the included RP2040 BIN-to-UF2
converter, avoiding an extra picotool download. Omit `-DPICO_NO_PICOTOOL=1` to use
the SDK's normal picotool UF2 generation instead; it can fetch/build picotool
if required (network access and a native toolchain needed).
If CMake cannot find the SDK, pass `-DPICO_SDK_PATH=/absolute/path/to/pico-sdk`.
On Windows, use the Raspberry Pi Pico SDK toolchain environment and equivalent
CMake commands; Bash `export` and `sudo apt` are Linux instructions.

Hold BOOTSEL while plugging the Pico into USB. Copy
`build/lc_metal_capture.uf2` (or the supplied prebuilt UF2) to the RPI-RP2 drive.
The board reboots and appears as a USB serial device. Use a data-capable cable.

## Collect labelled data

Create a PC Python environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r host/requirements.txt
python -m serial.tools.list_ports
```

Windows activation: `.venv\Scripts\activate`; use a port such as `COM5`.
On Linux the port is commonly `/dev/ttyACM0`. Your account may need permission
to use the serial device (often membership in the `dialout` group).
Close any other serial terminal while running the logger.

With a copper specimen held flat, 5 mm from the coil:

```sh
python host/capture.py --port /dev/ttyACM0 --label copper \
  --specimen copper_01 --gap-mm 5 --orientation flat_parallel \
  --cap-nf 47 --coil-uh 470 --session bench_01 \
  --count 100 --output data/captures.jsonl
```

Collect an empty-coil baseline and other specimens into the same file:

```sh
python host/capture.py --port /dev/ttyACM0 --label empty \
  --specimen none --gap-mm 0 --session bench_01 \
  --count 100 --output data/captures.jsonl
python host/plot_capture.py data/captures.jsonl --index 0
```

For the empty label, gap 0 is a placeholder meaning "no target", not a target
touching the coil. `--cap-nf` and `--coil-uh` are operator-entered metadata;
the firmware cannot detect which capacitor or coil is fitted. Power off before
changing capacitors manually. The same firmware works at nominal 23.2, 33.9
or 49.5 kHz with 100, 47 or 22 nF respectively and the nominal 470 µH coil.

`--interval 0.05` specifies a minimum interval between requests. This is not a
guaranteed 20 frames/s: text USB transfer and host processing may take longer.
Only validated frames are saved; an integrity/hardware fault stops the run.
Completed records remain in the append-only JSONL file. Each record contains a
unique capture UUID, UTC timestamp, session, label, specimen, gap, orientation,
capacitance, coil inductance, notes, firmware metadata and all raw samples.

## Terminal commands and wire protocol

Send `h` followed by newline for help, or `c` followed by newline for one capture.
USB CDC baud setting is immaterial; the logger opens at 115200 and asserts DTR.

Each capture is `FRAME <JSON>`, then 64 `DATA <start>,<32 uint16 samples>` lines,
then `END <frame id>`. Frame IDs restart at reboot; the host UUID avoids clashes.
CRC-32/ISO-HDLC is computed over all uint16 samples in little-endian order,
including the ADC error bits, with initial/final XOR 0xffffffff. Python
`zlib.crc32(struct.pack('<2048H', *samples))` produces the same value.

Fault fields include ADC error count, near-rail count, FIFO overflow/underflow,
capture timeout and PIO pulse-completion status. Near-rail means raw ADC ≤16
or ≥4079; this is a diagnostic heuristic, not a calibrated voltage check.

## Training discipline

Start by plotting resonant frequency and decay versus label and gap. If those
measurements do not separate classes, a neural network cannot recover material
information absent from the sensor. Use a plastic jig and several distinct
specimens per metal; retain session/specimen/gap metadata. Split train/test by
physical specimen or session rather than individual repeated captures.
For a feature model, use baseline-relative frequency, decay, approximate Q,
amplitude and, later, measurements at several capacitor settings.

## Verification

```sh
python -m unittest discover -s tests -v
```

The protocol tests do not emulate the RP2040 or analogue hardware. Build and
host checks cannot replace oscilloscope verification of pulse timing, ADC
waveform range, resonance and damping on the assembled circuit.

## Primary references

- Raspberry Pi ADC/PIO/DMA SDK APIs: https://www.raspberrypi.com/documentation/pico-sdk/hardware.html
- Raspberry Pi official ADC DMA example: https://github.com/raspberrypi/pico-examples/tree/master/adc/dma_capture
- Pico pinout and analogue power: https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf
- OPA2320 family pinout: https://www.ti.com/lit/ds/symlink/opa320.pdf
- TMUX1101 pinout: https://www.ti.com/lit/ds/symlink/tmux1101.pdf
