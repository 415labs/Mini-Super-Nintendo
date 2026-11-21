# How it works

## The SNES controller protocol

A SNES pad is a 16-bit shift register (a CD4021 or equivalent) with three inputs and one output:

| Line | Direction | Role |
|---|---|---|
| LATCH | host to pad | A 12 µs pulse that captures all button states |
| CLOCK | host to pad | Shifts the next bit out on each rising edge |
| DATA | pad to host | Serial output, **active low** (0 means pressed) |
| VCC, GND | power | |

A read takes one LATCH pulse and 16 clock pulses (6 µs low, 6 µs high each). The first bit is already on DATA while LATCH is high. Twelve bits are used, in this order:

```
B  Y  SELECT  START  UP  DOWN  LEFT  RIGHT  A  X  L  R
```

The host samples DATA at the end of each clock-low phase. The last four bits of the 16 are not used.

## The daemon (`software/snes_pad.c`)

1. Maps the GPIO registers from `/dev/gpiomem`. This uses the BCM2711 register layout, so it works on the Pi 4 only.
2. Drives LATCH and CLOCK, and reads both pads' DATA pins in the same pass with a single register read per clock (CLOCK and LATCH are shared; each pad has its own DATA).
3. Wakes up on an absolute `clock_nanosleep` schedule under `SCHED_FIFO` priority 80, with memory locked, so timing stays steady.
4. Compares each result with the previous one and, only when a button changes, writes events to a `uinput` virtual gamepad.
5. Takes an exclusive lock so a second copy cannot run at the same time.

The pull-up on each DATA pin makes an empty port read as "nothing pressed".

### Why a preempted read is harmless

The shift register is static CMOS. If the daemon is interrupted in the middle of a read, a clock phase is just stretched. The register holds its state until the next clock edge, so the bits are still correct.

### Event mapping

| SNES | Linux event |
|---|---|
| B | `BTN_SOUTH` |
| Y | `BTN_WEST` |
| A | `BTN_EAST` |
| X | `BTN_NORTH` |
| L / R | `BTN_TL` / `BTN_TR` |
| Select / Start | `BTN_SELECT` / `BTN_START` |
| D-pad | `ABS_X` / `ABS_Y` with values -1, 0, 1 |

The devices report USB-style IDs: vendor `0x1209`, product `1` for pad 1 and `2` for pad 2.

## The test tool (`software/snes_test.py`)

A pure-Python tool that runs the same protocol from the raw GPIO registers (slower than the daemon, but fine for testing) or reads the daemon's virtual gamepads with `--evdev`. Its wiring check detects an empty, stuck or unstable DATA line by comparing reads with the internal pull-up and pull-down. A connected pad drives DATA, so both pull directions read the same.
