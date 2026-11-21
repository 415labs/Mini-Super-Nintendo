# Troubleshooting

Start with the test tool. It has three views that help isolate where a fault is:

```bash
sudo systemctl stop snes-pad                      # free the pins (the tool refuses to run otherwise)
sudo python3 software/snes_test.py -n 2           # live view with a wiring check
sudo python3 software/snes_test.py --raw -n 2     # prints the 12 raw bits whenever they change
sudo systemctl start snes-pad
sudo python3 software/snes_test.py --evdev -n 2   # what RetroArch sees (daemon must be running)
```

## Many buttons flash at once, or buttons are missing, with the daemon running

**Cause: two copies of the daemon are running.** If you started `snes_pad` by hand while the service was already running, both fight over CLOCK and LATCH and every read is scrambled. The daemon now refuses to start a second copy, but older versions did not.

Check and fix:
```bash
pgrep -a snes_pad              # should print exactly one line
sudo pkill snes_pad
sudo systemctl stop snes-pad
sudo systemctl start snes-pad
```

To run it by hand for debugging, stop the service first.

## One port works, the other is flaky or dead

The wiring check in the test tool reports each port as `ok`, `stuck`, `empty` or `unstable`. Swap the pad into the working port to see whether the fault follows the pad or the port.

If it follows the port, the usual causes are, in order:

1. **A bad contact inside the socket, most often on GND (pin 7).** The pad's ground floats a little above the Pi's, so its DATA output can't pull the line fully low. Presses then register only some of the time. Reseat the plug, clean pin 7 with isopropyl alcohol and a swab, or replace the socket.
2. **A high-resistance wire or poor solder joint** on DATA or GND.
3. **Flux or a stray strand** leaking between DATA and the VCC row.

Multimeter checks (Pi off, daemon stopped, pad unplugged):

| Check | Expected |
|---|---|
| Socket pin to its hub pad, each of the five wires, while flexing the cord | under ~2 Ω and steady |
| DATA pad to VCC, GND, CLOCK and LATCH pads | open (OL or above 1 MΩ) |
| VCC pad to GND pad | open. A low reading is a short, so stop. |
| With the Pi on and a pad plugged in, VCC to GND | about 3.3 V |
| With `snes_test.py --raw` running, DATA to GND while idle | about 3.3 V |
| The same, while holding any button | under 0.4 V. A reading above 0.8 V means a resistive DATA or GND path. |

A symptom that gets much better with `--pulldown` is a sign of exactly this kind of weak low. Fix the contact rather than relying on the pull-down.

## "no pad detected" or a port shows `empty`

The test tool tells an empty port apart from a faulty one, and labels it "(no pad)" in the live view. If a pad is plugged in and the port still shows `empty`:
- Check that DATA reaches the correct GPIO: pad 1 on GPIO17 (header pin 11), pad 2 on GPIO10 (pin 19).
- Check CLOCK (GPIO27, pin 13) and LATCH (GPIO22, pin 15) by running `--raw`. If the display shows a button state stuck on one value, one of those two may not be reaching the pad.
- Confirm that SPI is disabled, since GPIO10 is its MOSI pin.

## All buttons are stuck on, or nothing ever changes

- Check that the pad's VCC is on header pin 17 (3V3) and GND on pin 9.
- Check that the red DATA wire is on the DATA pad and **not** on VCC. Cord colours vary, so re-identify each wire with a continuity test.

## `Permission denied` or `/dev/gpiomem` errors

Run the tools with `sudo`. The daemon is started as root by the service.

## `/dev/uinput` not found

```bash
sudo modprobe uinput
```
`install.sh` also makes this persistent across reboots.

## The service does not start

```bash
systemctl status snes-pad
journalctl -u snes-pad -n 30 --no-pager
```

On anything other than a Raspberry Pi 4, the daemon will not work because it reads BCM2711 registers directly.

## The pads work but the latency is not what I expected

See [LATENCY.md](LATENCY.md). The adapter adds well under a millisecond. Most of the remaining delay is in the emulator and the display.

## Still stuck?

Open an issue and include:
- the output of `sudo python3 software/snes_test.py --raw -n 1` (or `-n 2`)
- the output of `pgrep -a snes_pad` and `systemctl status snes-pad`
- which Pi model and OS you use, and a photo of the wiring if you can
