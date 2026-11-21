#!/usr/bin/env python3
"""Generate snes_hub_perfboard.svg: single-pad perfboard hub, Pi 4 <-> SNES pad 1 / pad 2.

Signal colours ARE the wire colours of the user's SNES extension cable:
  pin 1 green = 3.3 V power, 2 yellow = CLOCK, 3 white = LATCH, 4 red = DATA (NOT power), 7 black = GND
"""
import sys

W, H = 1220, 925
C = dict(v="#2e9e3a", clk="#f0c400", lat="#ffffff", d1="#d62728", d2="#d62728", gnd="#111111")
TC = dict(v="#1f7a2a", clk="#8a6d00", lat="#555555", d1="#c0201f", d2="#c0201f", gnd="#111111")
BOARD_BG = "#dfe9d8"
o = []


def a(s):
    o.append(s)


def text(x, y, s, size=12, anchor="start", weight="normal", fill="#111"):
    a(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
      f'font-weight="{weight}" fill="{fill}">{s}</text>')


def tag(x, y, s, size=11, weight="bold", fill="#111", right=False):
    """label with a board-coloured backing so it stays readable over holes/wires"""
    w = len(s) * size * 0.6 + 8
    x0 = x - w + 3 if right else x - 3
    a(f'<rect x="{x0}" y="{y-size}" width="{w}" height="{size+6}" rx="3" fill="{BOARD_BG}" opacity="0.97"/>')
    text(x0 + 4, y, s, size, weight=weight, fill=fill)


def wire(x0, x1, y, key, w=5):
    if C[key] == "#ffffff":                               # white wire gets a dark outline
        a(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#333333" stroke-width="{w+3}" '
          f'stroke-linecap="round"/>')
    a(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{C[key]}" stroke-width="{w}" '
      f'stroke-linecap="round"/>')


# ---- geometry ---------------------------------------------------------------
P = 32
BX, BY = 260, 130
NC, NR = 27, 11


def X(c):
    return BX + P / 2 + (c - 1) * P


def Y(r):
    return BY + P / 2 + (r - 1) * P


LET = "ABCDEFGHIJK"
ROW = {"gnd": 3, "d1": 4, "clk": 5, "lat": 6, "v": 7, "d2": 8}    # = Pi header order, pins 9..19
PI_C, P1_C, P2_C = 4, 14, 24

PI_NETS = ["gnd", "d1", "clk", "lat", "v", "d2"]
P1_NETS = [("gnd", "7 GND"), ("d1", "4 DATA"), ("clk", "2 CLK"), ("lat", "3 LATCH"), ("v", "1 VCC")]
P2_NETS = [("gnd", "7 GND"), ("clk", "2 CLK"), ("lat", "3 LATCH"), ("v", "1 VCC"), ("d2", "4 DATA")]
PI_NAME = {"d1": "DATA1", "v": "3V3", "clk": "CLK", "lat": "LATCH", "gnd": "GND", "d2": "DATA2"}
PI_REF = {"d1": "GPIO17 · pin 11", "v": "3V3 · pin 17", "clk": "GPIO27 · pin 13",
          "lat": "GPIO22 · pin 15", "gnd": "GND · pin 9", "d2": "GPIO10 · pin 19"}

a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
  f'font-family="Helvetica, Arial, sans-serif">')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(30, 38, "Perfboard hub: Raspberry Pi 4  ↔  SNES pad 1  ↔  SNES pad 2", 20, weight="bold")
text(30, 60, "Single-pad perfboard (no copper strips). 16 pads, 6 straight wire runs, no crossings. "
             "Top view; wires are drawn as if seen through the board.", 12.5, fill="#444")

# ---- board + holes ----------------------------------------------------------
a(f'<rect x="{BX}" y="{BY}" width="{NC*P}" height="{NR*P}" rx="10" fill="{BOARD_BG}" '
  f'stroke="#6b7f5e" stroke-width="2"/>')
for c in range(1, NC + 1):
    text(X(c), BY - 8, str(c), 10, anchor="middle", fill="#777")
for r in range(1, NR + 1):
    text(BX - 9, Y(r) + 4, LET[r - 1], 11, anchor="end", fill="#777", weight="bold")
for r in range(1, NR + 1):
    for c in range(1, NC + 1):
        a(f'<circle cx="{X(c)}" cy="{Y(r)}" r="8.5" fill="#e6cf94" stroke="#b8923a" stroke-width="1"/>')
        a(f'<circle cx="{X(c)}" cy="{Y(r)}" r="3" fill="#ffffff" stroke="#8a6d2a" stroke-width="0.8"/>')

# ---- wires (solder side, drawn through the board) ---------------------------
for key, c0, c1 in [("gnd", PI_C, P2_C), ("clk", PI_C, P2_C), ("lat", PI_C, P2_C), ("v", PI_C, P2_C),
                    ("d1", PI_C, P1_C), ("d2", PI_C, P2_C)]:
    wire(X(c0), X(c1), Y(ROW[key]), key)

# ---- optional decoupling cap C1 (across 3V3 row G and GND row C) ------------
for key in ("v", "gnd"):
    a(f'<circle cx="{X(9)}" cy="{Y(ROW[key])}" r="13" fill="none" stroke="#555" stroke-width="1.6" '
      f'stroke-dasharray="3 3"/>')
tag(X(9) + 16, Y(ROW["v"]) + 4, "C1", 11, fill="#555")
tag(X(9) + 16, Y(ROW["gnd"]) + 4, "C1", 11, fill="#555")


def pad(c, key):
    a(f'<circle cx="{X(c)}" cy="{Y(ROW[key])}" r="12" fill="{C[key]}" stroke="#111" stroke-width="1.2"/>')
    a(f'<circle cx="{X(c)}" cy="{Y(ROW[key])}" r="3.4" fill="#ffffff" stroke="#555" stroke-width="0.8"/>')


# ---- Pi block -----------------------------------------------------------------
for key in PI_NETS:
    pad(PI_C, key)
    y = Y(ROW[key])
    tag(X(PI_C) - 16, y + 4, PI_NAME[key], 11.5, fill=TC[key], right=True)
    text(BX - 28, y + 4, PI_REF[key], 12, anchor="end", fill="#222")
a(f'<rect x="{X(PI_C)-15}" y="{Y(3)-15}" width="30" height="{5*P+30}" rx="5" fill="none" '
  f'stroke="#2e6b3d" stroke-width="1.6" stroke-dasharray="5 3"/>')

# ---- Pad 1 / Pad 2 blocks -----------------------------------------------------
for c, nets_ in ((P1_C, P1_NETS), (P2_C, P2_NETS)):
    for key, lab in nets_:
        pad(c, key)
        tag(X(c) + 16, Y(ROW[key]) + 4, lab, 11.5, fill=TC[key])

# ---- group headers -------------------------------------------------------------
text(X(PI_C), BY - 28, "TO PI 4 PINS 9–19 (one 1×6 connector)", 12.5, anchor="middle",
     weight="bold", fill="#2e6b3d")
tag(X(P2_C) + 16, Y(ROW["d1"]) + 4, "leave empty", 10.5, weight="normal", fill="#6a6a6a")
text(X(P1_C), BY - 28, "SNES PAD 1 (socket cord)", 12.5, anchor="middle", weight="bold")
text(X(P2_C), BY - 28, "SNES PAD 2 (socket cord)", 12.5, anchor="middle", weight="bold")
text(BX - 28, BY - 8, "Pi side →", 11, anchor="end", fill="#2e6b3d")

ly = BY + NR * P + 24
text(BX, ly, "Coloured pad = used.  Plain hole = unused.  Dashed ring = optional 100 nF ceramic cap C1 "
             "across the 3V3 and GND wires (legs span 4 holes).", 11.5, fill="#444")
text(BX, ly + 17, "Green dashed box = 1×6 male pin header at C4–H4. One 1×6 Dupont female housing (or ribbon) "
                  "plugs onto it and onto Pi pins 9–19 in the same order (pin 9 = GND at C4).",
     11.5, fill="#2e6b3d")
text(BX, ly + 34, "Colours = your cord's wire colours: green 3.3 V power (pin 1), yellow CLOCK (2), "
                  "white LATCH (3), red DATA (4, NOT power), black GND (7).", 11.5, weight="bold", fill="#333")

# ---- wire list -----------------------------------------------------------------
ty = BY + NR * P + 92
text(30, ty, "Wire list: 6 wires, all straight along one row", 15, weight="bold")
rows = [
    ("gnd", "GND bus (black)",    "C4  →  C14  →  C24", "soldered at all three pads"),
    ("d1",  "DATA 1 (red)",       "D4  →  D14",              "Pi GPIO17 to pad 1 only (D24 stays empty)"),
    ("clk", "CLOCK bus (yellow)", "E4  →  E14  →  E24", "soldered at all three pads"),
    ("lat", "LATCH bus (white)",  "F4  →  F14  →  F24", "soldered at all three pads"),
    ("v",   "3V3 bus (green)",    "G4  →  G14  →  G24", "soldered at all three pads"),
    ("d2",  "DATA 2 (red)",       "H4  →  H24",              "Pi GPIO10 to pad 2 only (H14 stays empty)"),
]
for i, (key, nm, route, note) in enumerate(rows):
    y = ty + 28 + i * 24
    wire(36, 72, y - 4, key)
    text(84, y, nm, 13, weight="bold", fill=TC[key])
    text(250, y, route, 13)
    text(450, y, note, 12.5, fill="#444")

# ---- build notes ---------------------------------------------------------------
ny = ty + 28 + 6 * 24 + 18
a(f'<rect x="30" y="{ny}" width="1160" height="130" rx="8" fill="#fff7e6" stroke="#e0a030" stroke-width="1.4"/>')
text(44, ny + 22, "Build notes", 13, weight="bold", fill="#9a5b00")
notes = [
    "1.  Use insulated wire (26–30 AWG) on the solder side. Rows are only 2.54 mm apart, so bare wire can short 3V3 to GND if it sags.",
    "2.  Pad cables: cut the extension cord and solder each wire to the pad of the same colour (pad 1 = C14–G14, pad 2 = C24 and E24–H24). Pins 5 and 6 stay unconnected.",
    "3.  GREEN (pin 1) is 3.3 V power and goes to the 3V3 row (G). RED (pin 4) is DATA, NOT power. Pad labels show the SNES pin number; confirm colours with a continuity test.",
    "4.  Tie each cord to a spare hole (for example B16 or B26) so pulling the cable never tears a pad.",
    "5.  Before connecting the Pi: beep out 3V3 (row G) against GND (row C). There must be no connection. Then check every row for stray bridges to its neighbours.",
]
for i, n in enumerate(notes):
    text(44, ny + 44 + i * 18, n, 12, fill="#333")

a("</svg>")
open(sys.argv[1], "w").write("\n".join(o))
print("wrote", sys.argv[1])
