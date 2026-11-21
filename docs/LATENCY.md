# Latency and tuning

## How much latency does this add?

The adapter's added latency is the time between pressing a button and the daemon reporting it. On average it is half the polling period plus the time one read takes:

```
average added latency = poll_period / 2 + read_time
read_time             = half_clock_period × 27     (12 data bits)
```

| Settings | Poll rate | Read time | Average added | Worst case |
|---|---|---|---|---|
| **Default** `-r 1000 -t 6` | 1000 Hz | ~162 µs | **~0.66 ms** | ~1.2 ms |
| **Fast** `-r 4000 -t 3 -a 3` | 4000 Hz | ~81 µs | **~0.2 ms** | ~0.33 ms |
| **Fastest** `-r 8000 -t 2 -a 3` | 8000 Hz | ~54 µs | **~0.12 ms** | ~0.18 ms |

These are calculated figures for the polling stage. They do not include the kernel input path (microseconds), RetroArch's own frame timing, or the display.

## Versus a USB SNES pad

Typical cheap USB SNES pads are polled by the host at 100 to 125 Hz, which means 8 to 10 ms between reads. That adds about **4 to 5 ms on average and up to 8 to 10 ms in the worst case**. This GPIO adapter at its default settings is roughly 6 to 7 times faster, and at the fast settings 20 times faster or more. You can raise a USB pad's rate with `usbhid.jspoll=1` on the kernel command line, which brings it to about 1 ms polling. That narrows the gap but costs some CPU, and the pad's own firmware may still limit it.

One frame at 60 Hz is 16.7 ms. A 4 ms saving is a quarter of a frame, which is small but measurable, especially with run-ahead.

## Going faster

The default is conservative and works with every pad and cord length. To get to the fast settings:

1. **Reserve a CPU core** for the daemon. Edit the kernel command line (`/boot/firmware/cmdline.txt` on current Raspberry Pi OS, or `/boot/cmdline.txt` on older images such as RetroPie) and add `isolcpus=3` to the end of the single line. Reboot.
2. **Install with the tuned options:**
   ```bash
   bash install.sh -n 2 -r 4000 -t 3 -a 3
   ```
   `-a 3` pins the daemon to the reserved core.
3. **Test again** with `sudo python3 software/snes_test.py --evdev -n 2`. If any buttons are missed or flicker, go back to a slower `-t` (the clock is too fast for your cable or pad). Short cords tolerate faster clocks.

Try `-r 8000 -t 2 -a 3` for the fastest setting, if the pad keeps up. The daemon runs under real-time scheduling (`SCHED_FIFO`, priority 80). A preemption in the middle of a read only stretches a clock phase, which the pad's shift register ignores, so occasional delays do not corrupt data.

## Why GPIO is so fast

The daemon maps the GPIO registers directly through `/dev/gpiomem` and toggles CLOCK and LATCH in a tight loop with no library overhead. It reads both pads in a single pass using one register read per clock. It then emits input events only when a button changes.
