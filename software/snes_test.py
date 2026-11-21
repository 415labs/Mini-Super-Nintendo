#!/usr/bin/env python3
"""snes_test.py - check that your SNES pads are wired and working (Raspberry Pi 4).

Mode 1 (default): read the pads straight from the GPIO pins, same wiring as snes_pad.c.
    sudo systemctl stop snes-pad        # the daemon must not be running
    sudo python3 snes_test.py
    1. wiring check: tells you per pad whether a pad answers on its DATA line
    2. live view: every button lights up while you hold it
    3. Ctrl-C: report of which buttons were never seen on each pad

Mode 2: see what RetroArch will see (reads the virtual gamepads made by the daemon).
    sudo systemctl start snes-pad
    sudo python3 snes_test.py --evdev

No extra packages needed. Pi 4 only (BCM2711 registers via /dev/gpiomem).
Wiring (BCM): LATCH 22, CLOCK 27, DATA pad1 17, DATA pad2 10; pads powered from 3V3.
"""
import argparse
import mmap
import os
import select
import struct
import subprocess
import sys
import time

PIN_CLOCK, PIN_LATCH = 27, 22
PIN_DATA = [17, 10]                       # pad 1, pad 2
NAMES = ["B", "Y", "SELECT", "START", "UP", "DOWN", "LEFT", "RIGHT", "A", "X", "L", "R"]
ALL = 0xFFF

GPSET0, GPCLR0, GPLEV0, PUPPDN0 = 7, 10, 13, 57       # BCM2711 register word offsets
PULL_UP, PULL_DOWN = 1, 2


# --------------------------------------------------------------------------- GPIO
class Gpio:
    def __init__(self):
        fd = os.open("/dev/gpiomem", os.O_RDWR | os.O_SYNC)
        self.mm = mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        os.close(fd)
        self.r = memoryview(self.mm).cast("I")        # whole 32-bit register accesses

    def mode(self, pin, out):
        i, sh = pin // 10, (pin % 10) * 3
        self.r[i] = ((self.r[i] & ~(7 << sh)) & 0xFFFFFFFF) | ((1 if out else 0) << sh)

    def pull(self, pin, kind):
        i, sh = PUPPDN0 + pin // 16, (pin % 16) * 2
        self.r[i] = ((self.r[i] & ~(3 << sh)) & 0xFFFFFFFF) | (kind << sh)

    def hi(self, pin):
        self.r[GPSET0] = 1 << pin

    def lo(self, pin):
        self.r[GPCLR0] = 1 << pin

    def lev(self):
        return self.r[GPLEV0]

    def close(self):
        self.r.release()
        self.mm.close()


def delay(ns):
    end = time.perf_counter_ns() + ns
    while time.perf_counter_ns() < end:
        pass


def read_raw(g, half_ns, npads):
    """One SNES read. Returns per pad a 12-bit value where bit=1 means the DATA line was high
    (button released); order B Y SELECT START UP DOWN LEFT RIGHT A X L R."""
    raw = [0] * npads
    g.hi(PIN_LATCH)
    delay(2 * half_ns)
    g.lo(PIN_LATCH)
    delay(half_ns)
    for i in range(12):
        g.lo(PIN_CLOCK)
        delay(half_ns)
        lev = g.lev()
        for p in range(npads):
            if (lev >> PIN_DATA[p]) & 1:
                raw[p] |= 1 << i
        g.hi(PIN_CLOCK)
        delay(half_ns)
    return raw


def names_of(mask):
    return ", ".join(n for i, n in enumerate(NAMES) if mask >> i & 1) or "none"


def wiring_check(g, half_ns, npads):
    """A pad connected and powered drives DATA itself, so the reading is the same with the
    pin's pull-up and with its pull-down. A floating (unconnected) line just follows the pull."""
    for p in range(npads):
        g.pull(PIN_DATA[p], PULL_DOWN)
    time.sleep(0.005)
    dn = read_raw(g, half_ns, npads)
    for p in range(npads):
        g.pull(PIN_DATA[p], PULL_UP)
    time.sleep(0.005)
    up = read_raw(g, half_ns, npads)

    status = []
    print("Wiring check")
    for p in range(npads):
        tag = f"  Pad {p + 1} (DATA on GPIO{PIN_DATA[p]}): "
        if dn[p] == up[p]:
            pressed = ~up[p] & ALL
            if pressed == 0:
                status.append("ok")
                print(tag + "OK, pad answers, nothing pressed")
            elif pressed == ALL:
                status.append("stuck")
                print(tag + "PROBLEM: reads as all 12 buttons pressed. DATA is stuck low "
                            "(short to GND? pad unpowered? check VCC on 3V3)")
            else:
                status.append("ok")
                print(tag + f"OK, pad answers (held right now: {names_of(pressed)})")
        elif dn[p] == 0 and up[p] == ALL:
            status.append("empty")
            print(tag + "no pad detected (DATA floating). Normal if nothing is plugged into this port.\n"
                        "      If a pad IS plugged in: check VCC (green) on 3V3, GND (black), "
                        "DATA (red) on the right pin")
        else:
            status.append("unstable")
            print(tag + f"UNSTABLE: pull-down read {dn[p]:03x}, pull-up read {up[p]:03x}. "
                        "Loose or noisy wire, or too fast: try -t 20")
    print()
    return status


# --------------------------------------------------------------------------- display
class Display:
    def __init__(self, labels, footer=""):
        self.labels = labels
        self.n = len(labels)
        self.cur = [0] * self.n
        self.seen = [0] * self.n
        self.footer = footer
        self.started = False
        self.skip = set()                  # pads with nothing plugged in

    @staticmethod
    def fmt(mask):
        s = []
        for i, nm in enumerate(NAMES):
            s.append(f"\x1b[7;1m {nm} \x1b[0m" if mask >> i & 1 else f"\x1b[2m {nm} \x1b[0m")
        return "".join(s)

    def set(self, p, mask):
        self.cur[p] = mask
        self.seen[p] |= mask

    def render(self, extra=""):
        out = []
        if self.started:
            out.append(f"\x1b[{self.n + 2}A")
        for p in range(self.n):
            warn = "  <- all pressed? DATA stuck low" if self.cur[p] == ALL else ""
            out.append(f"{self.labels[p]}: {self.fmt(self.cur[p])}{warn}\x1b[K\n")
        out.append("\x1b[K\n")
        out.append(f"Ctrl-C to finish and get the report.  {self.footer}{extra}\x1b[K\n")
        sys.stdout.write("".join(out))
        sys.stdout.flush()
        self.started = True

    def report(self):
        print("\nReport")
        good = True
        for p in range(self.n):
            miss = [NAMES[i] for i in range(12) if not self.seen[p] >> i & 1]
            if p in self.skip and not self.seen[p]:
                print(f"  {self.labels[p]}: nothing plugged in, skipped")
            elif miss:
                good = False
                print(f"  {self.labels[p]}: NOT seen: {', '.join(miss)}")
            else:
                print(f"  {self.labels[p]}: all 12 buttons seen. OK")
        return good


# --------------------------------------------------------------------------- modes
def refuse_if_daemon(args):
    if args.force:
        return
    try:
        if subprocess.run(["systemctl", "is-active", "--quiet", "snes-pad"]).returncode == 0:
            sys.exit("The snes-pad service is running and owns the pins. Stop it first:\n"
                     "  sudo systemctl stop snes-pad\n(or use --force)")
    except FileNotFoundError:
        pass


def run_drive(args):
    """Wiring aid: toggle ONE pin high/low once a second so you can follow the signal
    with a multimeter (or LED + resistor) from the Pi to the hub pad. Unplug the pads first."""
    refuse_if_daemon(args)
    pins = {"clock": PIN_CLOCK, "latch": PIN_LATCH, "data1": PIN_DATA[0], "data2": PIN_DATA[1]}
    pin = pins[args.drive]
    try:
        g = Gpio()
    except PermissionError:
        sys.exit("Cannot open /dev/gpiomem. Run with sudo.")
    print(f"Driving GPIO{pin} ({args.drive}) HIGH/LOW once a second. Unplug the pads first.\n"
          "Measure between the matching hub pad and a GND pad: it should swing 0 V <-> 3.3 V.\n"
          "Ctrl-C to stop.\n")
    g.mode(pin, 1)
    level = 0
    try:
        while True:
            level ^= 1
            (g.hi if level else g.lo)(pin)
            sys.stdout.write(f"\r  GPIO{pin} = {'HIGH (3.3 V)' if level else 'LOW  (0 V)  '}")
            sys.stdout.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        g.lo(pin)
        g.mode(pin, 0)
        g.close()


def run_raw(g, half_ns, n, pulldown=False):
    """Print the 12 raw bits of each pad whenever they change (1 = released, 0 = pressed)."""
    if pulldown:
        print("PULL-DOWN MODE: if the pad stops driving DATA (loose wire, lost power) the line "
              "reads all zeros,\nso every dropout shows up as a DROPOUT line. Hold START and "
              "wiggle things one at a time.\n")
    print("Raw view: a line is printed whenever a pad's 12 bits change.\n"
          "Press ONE button at a time, hold it for a second, release. Start with B.\n"
          "Bit order: " + " ".join(NAMES) + "\n"
          "Ctrl-C to stop.\n")
    last = [None] * n
    t0 = time.perf_counter()
    try:
        while True:
            raw = read_raw(g, half_ns, n)
            for p in range(n):
                if raw[p] != last[p]:
                    bits = "".join("1" if raw[p] >> i & 1 else "0" for i in range(12))
                    note = ("   <-- DROPOUT: pad not driving DATA (open wire, lost power or bad contact)"
                            if raw[p] == 0 and pulldown else "")
                    print(f"{time.perf_counter() - t0:7.2f}s  Pad {p + 1}: {bits}   "
                          f"pressed: {names_of(~raw[p] & ALL)}{note}")
                    last[p] = raw[p]
            time.sleep(0.002)
    except KeyboardInterrupt:
        print()
    return True


def run_gpio(args):
    n = args.pads
    refuse_if_daemon(args)
    try:
        g = Gpio()
    except PermissionError:
        sys.exit("Cannot open /dev/gpiomem. Run with sudo.")
    half_ns = int(args.half_us * 1000)
    try:
        g.mode(PIN_LATCH, 1)
        g.lo(PIN_LATCH)
        g.mode(PIN_CLOCK, 1)
        g.hi(PIN_CLOCK)
        for p in range(n):
            g.mode(PIN_DATA[p], 0)
        status = [] if args.no_check else wiring_check(g, half_ns, n)
        for p in range(n):
            g.pull(PIN_DATA[p], PULL_DOWN if args.pulldown else PULL_UP)
        if args.raw:
            return run_raw(g, half_ns, n, args.pulldown)
        empty = {p for p, s in enumerate(status) if s == "empty"}
        print("Live view: press EVERY button on each pad that is plugged in.\n")
        disp = Display([f"Pad {p + 1}" + (" (no pad)" if p in empty else "") for p in range(n)])
        disp.skip = empty
        count, t0 = 0, time.perf_counter()
        hz = 0.0
        last = 0.0
        try:
            while True:
                raw = read_raw(g, half_ns, n)
                for p in range(n):
                    disp.set(p, ~raw[p] & ALL)
                count += 1
                now = time.perf_counter()
                if now - t0 >= 1.0:
                    hz, count, t0 = count / (now - t0), 0, now
                if now - last >= 1 / 30:
                    disp.render(f" (sampling {hz:.0f} Hz in Python)")
                    last = now
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        return disp.report()
    finally:
        g.mode(PIN_LATCH, 0)
        g.mode(PIN_CLOCK, 0)
        g.close()


EV_KEY, EV_ABS = 1, 3
KEYBIT = {0x130: 0, 0x134: 1, 0x13A: 2, 0x13B: 3, 0x131: 8, 0x133: 9, 0x136: 10, 0x137: 11}
EV_FMT = "llHHi"                                   # struct input_event for this architecture
EV_SZ = struct.calcsize(EV_FMT)


def find_devices():
    found = {}
    with open("/proc/bus/input/devices") as f:
        blocks = f.read().strip().split("\n\n")
    for b in blocks:
        name = handler = None
        for ln in b.splitlines():
            if ln.startswith("N: Name="):
                name = ln.split("=", 1)[1].strip().strip('"')
            elif ln.startswith("H: Handlers="):
                for tok in ln.split("=", 1)[1].split():
                    if tok.startswith("event"):
                        handler = "/dev/input/" + tok
        if name and handler and name.startswith("SNES GPIO Pad "):
            found[int(name.split()[-1]) - 1] = handler
    return found


def run_evdev(args):
    devs = find_devices()
    if not devs:
        sys.exit("No 'SNES GPIO Pad' gamepads found. Start the daemon first:\n"
                 "  sudo systemctl start snes-pad && sudo systemctl status snes-pad")
    n = max(devs) + 1
    try:
        fds = {os.open(path, os.O_RDONLY | os.O_NONBLOCK): p for p, path in devs.items()}
    except PermissionError:
        sys.exit("Cannot read /dev/input/event*. Run with sudo.")
    print(f"Reading {len(devs)} gamepad(s) made by the daemon: "
          + ", ".join(f"Pad {p + 1} = {path}" for p, path in sorted(devs.items())) + "\n")
    disp = Display([f"Pad {p + 1}" for p in range(n)], footer="(events as RetroArch sees them) ")
    mask = [0] * n
    try:
        while True:
            ready, _, _ = select.select(list(fds), [], [], 0.05)
            for fd in ready:
                p = fds[fd]
                try:
                    data = os.read(fd, EV_SZ * 64)
                except BlockingIOError:
                    continue
                for off in range(0, len(data) - EV_SZ + 1, EV_SZ):
                    _, _, t, c, v = struct.unpack_from(EV_FMT, data, off)
                    if t == EV_KEY and c in KEYBIT:
                        bit = 1 << KEYBIT[c]
                        mask[p] = (mask[p] | bit) if v else (mask[p] & ~bit)
                    elif t == EV_ABS and c == 0:                       # X: LEFT bit 6, RIGHT bit 7
                        mask[p] &= ~0xC0
                        mask[p] |= 0x40 if v < 0 else 0x80 if v > 0 else 0
                    elif t == EV_ABS and c == 1:                       # Y: UP bit 4, DOWN bit 5
                        mask[p] &= ~0x30
                        mask[p] |= 0x10 if v < 0 else 0x20 if v > 0 else 0
                    disp.set(p, mask[p])
            disp.render()
    except KeyboardInterrupt:
        pass
    return disp.report()


def main():
    global PIN_CLOCK, PIN_LATCH
    ap = argparse.ArgumentParser(description="Test SNES pads wired to a Raspberry Pi 4")
    ap.add_argument("--evdev", action="store_true",
                    help="read the daemon's virtual gamepads instead of the GPIO pins")
    ap.add_argument("-n", "--pads", type=int, choices=(1, 2), default=2, help="pads to test (default 2)")
    ap.add_argument("-t", "--half-us", type=float, default=10.0,
                    help="half clock period in microseconds (default 10; Python is slow anyway)")
    ap.add_argument("--no-check", action="store_true", help="skip the wiring check")
    ap.add_argument("--force", action="store_true", help="run even if the snes-pad service is active")
    ap.add_argument("--data2", type=int, default=10, metavar="GPIO",
                    help="BCM GPIO that pad 2 DATA is wired to (default 10 = header pin 19; "
                         "23 = header pin 16, the pin an earlier drawing used)")
    ap.add_argument("--raw", action="store_true",
                    help="print the raw 12 bits whenever they change (diagnosis)")
    ap.add_argument("--pulldown", action="store_true",
                    help="use a pull-down on DATA so a dropped connection shows as all-zeros "
                         "(DROPOUT) instead of 'nothing pressed'; use with --raw")
    ap.add_argument("--swap-cl", action="store_true",
                    help="swap the CLOCK and LATCH pins in software (test with the pad in port 2 only: "
                         "if it then works, CLOCK and LATCH are swapped at that port)")
    ap.add_argument("--drive", choices=("clock", "latch", "data1", "data2"),
                    help="wiring aid: toggle one pin once a second, unplug pads first, "
                         "then measure it at the hub with a multimeter")
    args = ap.parse_args()
    PIN_DATA[1] = args.data2
    if args.swap_cl:
        PIN_CLOCK, PIN_LATCH = PIN_LATCH, PIN_CLOCK
        print(f"NOTE: CLOCK and LATCH swapped in software (clock=GPIO{PIN_CLOCK}, latch=GPIO{PIN_LATCH})\n")
    if args.drive:
        run_drive(args)
        sys.exit(0)
    ok = run_evdev(args) if args.evdev else run_gpio(args)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
