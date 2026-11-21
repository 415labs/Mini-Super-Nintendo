#!/usr/bin/env python3
"""Generate snes_pi_wiring.svg: Raspberry Pi 4 <-> two SNES controller sockets.

Net colours ARE the wire colours of the user's SNES extension cable, so the drawing and
the cord always agree:
  socket pin 1 green  = 3.3 V power      socket pin 2 yellow = CLOCK
  socket pin 3 white  = LATCH            socket pin 4 red    = DATA (NOT power)
  socket pin 7 black  = GND
"""
import sys

W, H = 1120, 800
C = dict(v="#2e9e3a", clk="#f0c400", lat="#ffffff", d1="#d62728", d2="#d62728",
         gnd="#111111", nc="#9aa0a6")                     # fills
TC = dict(v="#1f7a2a", clk="#8a6d00", lat="#555555", d1="#c0201f", d2="#c0201f",
          gnd="#111111", nc="#888888")                    # text colours
ON = dict(v="#ffffff", clk="#222222", lat="#222222", d1="#ffffff", d2="#ffffff",
          gnd="#ffffff", nc="#ffffff")                    # text on top of a fill
o = []


def a(s):
    o.append(s)


def line(pts, color, w=2.6):
    p = " ".join(f"{x},{y}" for x, y in pts)
    if color == "#ffffff":                                # white wire: dark outline underneath
        a(f'<polyline points="{p}" fill="none" stroke="#333333" stroke-width="{w+3}" '
          f'stroke-linejoin="round" stroke-linecap="round"/>')
    a(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{w}" '
      f'stroke-linejoin="round" stroke-linecap="round"/>')


def dot(x, y, color, r=4.6):
    a(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" stroke="#333333" stroke-width="1"/>')


def text(x, y, s, size=13, anchor="start", weight="normal", fill="#111"):
    a(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
      f'font-weight="{weight}" fill="{fill}">{s}</text>')


def rect(x, y, w, h, fill="none", stroke="#222", sw=1.6, rx=6):
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
      f'stroke="{stroke}" stroke-width="{sw}"/>')


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
  f'font-family="Helvetica, Arial, sans-serif">')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(30, 36, "Two original SNES controllers on a Raspberry Pi 4 (GPIO, 3.3 V)", 20, weight="bold")
text(30, 58, "LATCH, CLOCK, 3V3 and GND are shared by both pads; each pad has its own DATA line. "
             "All six Pi connections sit on one row of the header (pins 9, 11, 13, 15, 17, 19).",
     13, fill="#444")

# ---------------------------------------------------------------- Fig. 1
PI_X0, PI_X1, PI_Y0, PI_Y1 = 40, 230, 85, 470
rect(PI_X0, PI_Y0, PI_X1 - PI_X0, PI_Y1 - PI_Y0, fill="#f3f6f4", stroke="#2e6b3d", sw=2)
text(PI_X0 + 12, PI_Y0 + 20, "Raspberry Pi 4 · GPIO", 14, weight="bold", fill="#2e6b3d")
text(PI_X0 + 12, PI_Y0 + 36, "one row: header pins 9–19", 10.5, fill="#2e6b3d")

# (key, label, pin-ref, Pi terminal y, bus x, socket pin number)
nets = [
    ("v",   "3V3",   "pin 17",               395, 300, 1),
    ("clk", "CLOCK", "GPIO27 · pin 13", 270, 330, 2),
    ("lat", "LATCH", "GPIO22 · pin 15", 335, 360, 3),
    ("gnd", "GND",   "pin 9",                140, 390, 7),
]
data = [
    ("d1", "DATA 1", "GPIO17 · pin 11", 200, 480, 4, 0),
    ("d2", "DATA 2", "GPIO10 · pin 19", 435, 510, 4, 1),
]

SOCK_X = 560
P1_Y = {1: 125, 2: 155, 3: 185, 4: 215, 5: 255, 6: 285, 7: 315}
P2_Y = {k: v + 295 for k, v in P1_Y.items()}
PN = {1: "VCC (3.3 V)", 2: "CLOCK", 3: "LATCH", 4: "DATA", 5: "N/C", 6: "N/C", 7: "GND"}
PKEY = {1: "v", 2: "clk", 3: "lat", 4: None, 5: "nc", 6: "nc", 7: "gnd"}

# sockets
for idx, (ys, title) in enumerate(((P1_Y, "P1 · SNES socket, player 1"),
                                    (P2_Y, "P2 · SNES socket, player 2"))):
    top, bot = ys[1] - 32, ys[7] + 26
    rect(SOCK_X, top, 190, bot - top, fill="#fafafa")
    text(SOCK_X, top - 8, title, 13, weight="bold")
    gy = (ys[4] + ys[5]) / 2                              # gap between pins 4 and 5
    a(f'<line x1="{SOCK_X+4}" y1="{gy}" x2="{SOCK_X+186}" y2="{gy}" stroke="#bbb" '
      f'stroke-width="1" stroke-dasharray="3 3"/>')
    for k in range(1, 8):
        key = PKEY[k]
        if key is None:
            key = "d1" if idx == 0 else "d2"
        dot(SOCK_X, ys[k], C[key], 7)
        text(SOCK_X + 16, ys[k] + 4, f"{k}", 12, weight="bold")
        text(SOCK_X + 34, ys[k] + 4, PN[k], 12, fill="#222" if k not in (5, 6) else "#888")

# buses
for key, label, pinref, piy, bx, spin in nets:
    ys = [piy, P1_Y[spin], P2_Y[spin]]
    line([(bx, min(ys)), (bx, max(ys))], C[key])
    line([(PI_X1, piy), (bx, piy)], C[key])
    line([(bx, P1_Y[spin]), (SOCK_X, P1_Y[spin])], C[key])
    line([(bx, P2_Y[spin]), (SOCK_X, P2_Y[spin])], C[key])
    for y in ys:
        dot(bx, y, C[key])

# separate data lines
for key, label, pinref, piy, vx, spin, which in data:
    ys = P1_Y if which == 0 else P2_Y
    line([(PI_X1, piy), (vx, piy), (vx, ys[spin]), (SOCK_X, ys[spin])], C[key])

# redraw socket pin dots on top of the wire ends
for idx, ys in enumerate((P1_Y, P2_Y)):
    for k in range(1, 8):
        key = PKEY[k] or ("d1" if idx == 0 else "d2")
        dot(SOCK_X, ys[k], C[key], 7)

# Pi terminals + inside labels
terms = [(n[3], n[1], n[2], n[0]) for n in nets] + [(d[3], d[1], d[2], d[0]) for d in data]
for y, label, pinref, key in terms:
    dot(PI_X1, y, C[key], 6)
    text(PI_X0 + 12, y + 4, label, 13, weight="bold", fill=TC[key])
    text(PI_X1 - 12, y + 4, pinref, 11, anchor="end", fill="#333")

text(PI_X0, 500, "●  = wires connected here", 11, fill="#555")
text(PI_X0, 516, "Crossing with no dot = not connected", 11, fill="#555")

# colour legend
LX, LY = 40, 548
text(LX, LY, "Colour = wire colour on your SNES cord", 12, weight="bold")
legend = [("v", "GREEN", "3.3 V power (pin 1)"), ("clk", "YELLOW", "CLOCK (pin 2)"),
          ("lat", "WHITE", "LATCH (pin 3)"), ("d1", "RED", "DATA (pin 4), NOT power"),
          ("gnd", "BLACK", "GND (pin 7)")]
for i, (k, nm, desc) in enumerate(legend):
    y = LY + 22 + i * 20
    dot(LX + 8, y - 4, C[k], 7)
    text(LX + 24, y, f"{nm}: {desc}", 11.5, weight="bold" if k == "d1" else "normal",
         fill="#c0201f" if k == "d1" else "#111")

# ---------------------------------------------------------------- Fig. 2 (header)
HX = 800
text(HX, 96, "Pi 4 header: one row, pins 9–19", 14, weight="bold")
text(HX, 114, "Pin 1 end at top; odd pins = inner row,", 11, fill="#555")
text(HX, 128, "even pins = row nearest the board edge.", 11, fill="#555")
rows = [
    (9,  "GND",                  "gnd", 10, "GPIO15 (unused)"),
    (11, "GPIO17 · DATA 1", "d1",  12, "GPIO18 (unused)"),
    (13, "GPIO27 · CLOCK",  "clk", 14, "GND (spare)"),
    (15, "GPIO22 · LATCH",  "lat", 16, "GPIO23 (unused)"),
    (17, "3V3",                  "v",   18, "GPIO24 (unused)"),
    (19, "GPIO10 · DATA 2", "d2",  20, "GND (spare)"),
]
cx_odd, cx_even = HX + 100, HX + 142
y0 = 160
for i, (po, lo, ko, pe, le) in enumerate(rows):
    y = y0 + i * 34
    rect(cx_odd - 14, y - 14, 28, 28, fill=C[ko], stroke="#222", sw=1.2, rx=3)
    text(cx_odd, y + 4, str(po), 12, anchor="middle", weight="bold", fill=ON[ko])
    text(cx_odd - 22, y + 4, lo, 12, anchor="end")
    rect(cx_even - 14, y - 14, 28, 28, fill="#e8eaed", stroke="#999", sw=1.0, rx=3)
    text(cx_even, y + 4, str(pe), 12, anchor="middle", fill="#666")
    text(cx_even + 22, y + 4, le, 12, fill="#888")

# ---------------------------------------------------------------- Fig. 3 (connector)
CY = 395
text(HX, CY, "SNES socket on the extension cord", 14, weight="bold")
text(HX, CY + 18, "Looking into the socket. The gap sits between pins 4 and 5;", 11, fill="#555")
text(HX, CY + 32, "the square end is pin 1, the angled end is pin 7.", 11, fill="#555")
bx0, bx1, by0, by1 = 815, 1090, CY + 52, CY + 102
a(f'<path d="M{bx0},{by0} L{bx1-22},{by0} L{bx1},{by0+22} L{bx1},{by1-22} L{bx1-22},{by1} '
  f'L{bx0},{by1} Z" fill="#fafafa" stroke="#222" stroke-width="1.8" stroke-linejoin="round"/>')
px = [835, 871, 907, 943, 997, 1033, 1069]
sig = ["3V3", "CLK", "LATCH", "DATA", "N/C", "N/C", "GND"]
sk = ["v", "clk", "lat", "d1", "nc", "nc", "gnd"]
col_name = ["green", "yellow", "white", "red", "", "", "black"]
py = by0 + 25
for i in range(7):
    a(f'<circle cx="{px[i]}" cy="{py}" r="11" fill="{C[sk[i]]}" stroke="#333" stroke-width="1"/>')
    text(px[i], py + 4, str(i + 1), 12, anchor="middle", weight="bold", fill=ON[sk[i]])
    text(px[i], by1 + 17, sig[i], 11, anchor="middle", weight="bold", fill="#222")
    text(px[i], by1 + 32, col_name[i] if col_name[i] else "–", 10.5, anchor="middle",
         fill=TC[sk[i]] if col_name[i] else "#888")
text(bx0, by1 + 58, "Pin colour = wire colour on your extension cable.", 11, fill="#555")
text(bx0, by1 + 72, "RED is DATA, not power. Power is GREEN (pin 1).", 11, weight="bold", fill="#c0201f")

# ---------------------------------------------------------------- notes
ny = 700
rect(30, ny - 26, 1060, 110, fill="#fff7e6", stroke="#e0a030", sw=1.4)
text(44, ny - 6, "Read before powering up", 13, weight="bold", fill="#9a5b00")
notes = [
    "1.  GREEN cord wire (pin 1) = 3.3 V power: connect to 3V3 (pin 17) only. RED = DATA, not power. Never use 5 V (DATA would put 5 V on a 3.3 V-only Pi pin).",
    "2.  Cut the cord and use the SOCKET half. Pins 5 and 6 stay unconnected. Confirm each wire's colour against its socket pin with a continuity test before wiring.",
    "3.  A pad that is not plugged in reads as 'nothing pressed' (internal pull-up on DATA), so one pad or two both work. Plug pads in with the Pi powered off.",
    "4.  If reads are flaky on a long cord, raise the half-period: sudo ./snes_pad -t 8.   Short cord, want faster: -t 3.",
    "5.  GPIO10 (pin 19) is SPI0 MOSI: keep SPI disabled (raspi-config, Interface Options, SPI, No). Mark pin 9 (GND) on your 1x6 connector.",
]
for i, n in enumerate(notes):
    text(44, ny + 14 + i * 16, n, 11.5, fill="#333")

a("</svg>")
open(sys.argv[1], "w").write("\n".join(o))
print("wrote", sys.argv[1])
