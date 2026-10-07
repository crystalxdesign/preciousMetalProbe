# Wiring and component list

Use the specified packages: **OPA2320AID, SOIC-8** (not OPA2320S), and
**TMUX1101DBVR, SOT-23-5**, with pins numbered as in their datasheets.
The schematic is a connectivity drawing, not a PCB layout or footprint guide.

## Nets

| Net | Connections |
|---|---|
| +3V3 | Pico pin 36; U1 pin 8; U2 pin 5; R1 top; U2 S pin 2; C5/C6/C7 supply ends |
| AGND | Pico pin 33; U1 pin 4; U2 pin 3; R2 bottom; C1/C2/C4/C5/C6/C7 ground ends; R5 bottom |
| MID | R1 bottom; R2 top; C1/C2 positive/signal ends; U1A + input pin 3 |
| BIAS | U1A output pin 1; U1A − input pin 2; L1 lower terminal; C3 lower terminal |
| EXCITE | Pico GP15 physical pin 20; U2 SEL pin 4; R5 top |
| SWITCH_OUT | U2 D pin 1; R3 input end |
| TANK | R3 output end; L1 upper terminal; C3 upper terminal; U1B + input pin 5 |
| BUFFER_OUT | U1B output pin 7; U1B − input pin 6; R4 input end |
| ADC_IN | R4 output end; C4 signal end; Pico GP26 / ADC0 physical pin 31 |

L1 and C3 are both connected between TANK and BIAS. Neither LC terminal is
connected directly to ground. There is no power or external signal connection
to Pico ADC_VREF. All grounds are common; route analogue returns to AGND without
running switch/USB return currents through long coil or ADC ground leads.

## Parts

| Ref | Value / part | Notes |
|---|---|---|
| U1 | OPA2320AID | Dual unity-gain-stable rail-to-rail amplifier; SOIC-8 |
| U2 | TMUX1101DBVR | Active-high analogue switch; SOT-23-5 |
| R1/R2 | 10 kΩ each | 1% or better, matched values for midrail |
| R3 | 330 Ω | Excitation resistor; increase if tank amplitude is excessive |
| R4 | 100 Ω | ADC buffer isolation |
| R5 | 100 kΩ | SEL reset pulldown |
| L1 | ~470 µH measured air-core coil | Start with 40–60 mm plastic former; adjust winding to measured value |
| C1 | 10 µF | MID filter, ≥6.3 V; if electrolytic, positive to MID |
| C2 | 100 nF | MID filter |
| C3 | 47 nF | Stable C0G/NP0 or polypropylene film; ≥16 V |
| C4 | 4.7 nF | ADC transient isolation; place at GP26 |
| C5 | 100 nF | Directly between U1 pins 8 and 4 |
| C6 | 100 nF | Directly between U2 pins 5 and 3 |
| C7 | 10 µF | Analogue supply bulk capacitor; positive to +3V3 |

Do not put a large capacitor directly on U1A's output/BIAS without checking
amplifier stability. C1/C2 filter the divider input, not the buffer output.
Keep the analogue circuit compact and the coil mechanically fixed. Avoid a
ground plane under the sensing coil and metal hardware in the sensing region.

## Bring-up

1. Leave GP26 disconnected. Inspect wiring and package orientation.
2. Connect USB power. Check +3V3, MID and BIAS; the latter two should be near 1.65 V.
3. Flash firmware. With an oscilloscope, request `c\n` and check GP15 is high
   for 5 µs and returns low. It should remain low while idle/reset.
4. Scope TANK against AGND with a high-impedance ×10 probe. Check the resting
   1.65 V and a decaying sinusoid after excitation. Expect around 33.9 kHz
   for the nominal measured L/C, modified by coil losses and nearby targets.
5. Check U1B output and ADC_IN remain within 0.3–3.0 V comfortably for all intended
   targets and gaps. Adjust R3/pulse if necessary; do not rely on input clamp diodes.
6. Connect GP26, run the logger and inspect an empty-coil waveform.
7. Remove the scope probe before final training collection if its capacitance
   materially changes the tank. Keep cabling and surroundings consistent.
8. Use a plastic jig to introduce targets and record their actual distances.

If the ring decays too quickly, check coil resistance/losses, incorrect connections,
conductive material behind the coil and unintended loading. If there is no ring,
check excitation polarity, switch supply, SEL and U1 buffer wiring. A flat ADC
trace near either rail requires correcting the hardware before collection.
