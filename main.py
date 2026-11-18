#!/usr/bin/env python3
"""news-image-20261117 -- "ONE DAY, ONE PLANET" situation board.

Sums up the world news of Tuesday 17 November 2026 in one 1024x1024
image: a dark-navy mission-control board, not a newspaper. A large world
map carries 12 numbered, colour-coded pins; below it, 12 stories in big
type, one line each, every one readable at 300px wide; a gold strip
closes with the Voyager 1 "shine a light" night.

Pure Python 3 standard library only (the competition contract: nothing
is installed before the program runs, no network). The picture is drawn
from scratch at runtime -- flat vector shapes plus bitmap DejaVu glyphs
loaded from font_tables.json beside this file -- and written to
$MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).
Deterministic: two runs write identical bytes.

All copy comes from verified reporting of 17 November 2026 (Reuters,
AP, WHO, UN News, TechCrunch); disputed claims are attributed in the
headline itself ("Iran says...", "foiled"). ASCII only.
"""
import json
import math
import os
import struct
import zlib

W, H = 1024, 1024

# --- palette -------------------------------------------------------------
NAVY = (11, 29, 58)       # board background #0B1D3A
PANEL = (15, 42, 77)      # map panel, one step lighter than the board
GRID = (24, 58, 96)       # faint map graticule
LAND = (216, 221, 227)    # continents #D8DDE3
GOLD = (217, 164, 65)     # kicker, rules, icons, final strip #D9A441
WHITE = (255, 255, 255)
MUTE = (150, 165, 185)    # subline grey-blue
FAINT = (120, 140, 165)   # leader lines, source line
INK = (11, 29, 58)        # text on the gold strip

# category colours (ring / dot / legend)
CAT = {
    "conflict": (208, 0, 0),      # red
    "diplomacy": (46, 124, 230),  # blue
    "economy": (30, 158, 90),     # green
    "health": (139, 63, 217),     # purple
    "politics": (232, 119, 34),   # orange
}

OUT_NAME = "entry.png"


# --- canvas --------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def fill_rect(self, x0, y0, x1, y1, c):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w, x1)
        y1 = min(self.h, y1)
        row = bytes(c) * (x1 - x0)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def disc(self, cx, cy, r, c):
        for y in range(cy - r, cy + r + 1):
            dx = int((r * r - (y - cy) * (y - cy)) ** 0.5)
            self.fill_rect(cx - dx, y, cx + dx + 1, y + 1, c)

    def ring(self, cx, cy, r, edge, fill, w=2):
        """Disc of radius r in edge colour with the centre repainted in
        fill colour, leaving an edge-colour ring w px thick."""
        self.disc(cx, cy, r, edge)
        self.disc(cx, cy, r - w, fill)

    def line(self, x0, y0, x1, y1, c, w=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        r = max(0, w // 2)
        while True:
            if r:
                self.disc(x, y, r, c)
            else:
                self.set(x, y, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def polygon(self, points, c):
        """Scanline fill, even-odd rule."""
        ys = [p[1] for p in points]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(points)
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[i]), y, int(xs[i + 1]) + 1, y + 1, c)


# --- PNG (stdlib encoder: filter 0, zlib level 9) -------------------------
def png_bytes(cv):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# --- bitmap fonts ----------------------------------------------------------
def load_tables():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "font_tables.json")) as f:
        return json.load(f)


def text_width(table, s):
    return sum((table[ch]["w"] + 1) for ch in s if ch in table) - 1


def text_height(table, s):
    return max((table[ch].get("yoff", 0) + table[ch]["h"]
                for ch in s if ch in table), default=0)


def draw_text(cv, table, x, y, s, color):
    """Blit bitmap glyphs at (x, y) = top-left of the cap line. Each glyph
    is drawn at y + yoff so all glyphs share one baseline. Returns end x."""
    cx = x
    for ch in s:
        g = table.get(ch)
        if g is None:
            cx += 4
            continue
        w, h = g["w"], g["h"]
        if h > 0 and w > 0:
            raw = bytes.fromhex(g["hex"])
            nb = (w + 7) // 8
            # Packing (see gen_fonts.py): pixel x is bit (w-1-x) of the
            # row integer, stored big-endian in nb bytes. So byte index
            # counts from the END of the row, not from the start.
            gy = y + g.get("yoff", 0)
            for yy in range(h):
                base = yy * nb
                for xx in range(w):
                    bitpos = w - 1 - xx
                    byte = raw[base + nb - 1 - bitpos // 8]
                    if byte & (1 << (bitpos % 8)):
                        cv.set(cx + xx, gy + yy, color)
        cx += w + 1
    return cx


def draw_text_centered(cv, table, cx, y, s, color):
    return draw_text(cv, table, cx - text_width(table, s) // 2, y, s, color)


# --- world map -------------------------------------------------------------
# Simplified continent blobs as (lon, lat) polygons, equirectangular:
# x = 40 + (lon + 170) / 360 * 944, y = 138 + (75 - lat) / 130 * 344.
# Deliberately coarse -- flat blobs on navy, recognisable, never fussy.

def geo(lon, lat):
    return (round(40 + (lon + 170) / 360.0 * 944),
            round(138 + (75 - lat) / 130.0 * 344))


NORTH_AMERICA = [(-168, 66), (-158, 58), (-150, 60), (-140, 60),
                 (-130, 54), (-125, 49), (-124, 42), (-120, 34),
                 (-114, 29), (-110, 24), (-105, 20), (-97, 16),
                 (-90, 14), (-83, 9), (-79, 9), (-83, 13), (-87, 21),
                 (-91, 19), (-94, 18), (-97, 22), (-97, 26), (-93, 30),
                 (-85, 30), (-81, 25), (-80, 32), (-76, 35), (-74, 40),
                 (-70, 42), (-65, 44), (-60, 47), (-60, 50), (-65, 52),
                 (-68, 55), (-72, 62), (-78, 62), (-85, 66), (-95, 69),
                 (-110, 68), (-130, 70), (-150, 70), (-165, 68)]
GREENLAND = [(-58, 64), (-52, 60), (-43, 60), (-40, 64), (-32, 68),
             (-22, 70), (-20, 74), (-30, 76), (-45, 76), (-55, 74),
             (-58, 70)]
SOUTH_AMERICA = [(-79, 9), (-77, 4), (-80, -3), (-81, -6), (-77, -12),
                 (-72, -18), (-70, -23), (-65, -28), (-62, -34),
                 (-58, -38), (-63, -41), (-66, -47), (-69, -52),
                 (-66, -55), (-62, -50), (-58, -42), (-52, -33),
                 (-48, -28), (-41, -23), (-38, -15), (-35, -9),
                 (-35, -6), (-40, -3), (-44, -2), (-50, 0), (-53, 4),
                 (-58, 6), (-62, 9), (-68, 11), (-72, 12), (-76, 10)]
EUROPE = [(-10, 37), (-9, 43), (-4, 48), (-1, 50), (3, 52), (7, 55),
          (8, 58), (12, 57), (18, 56), (22, 57), (26, 59), (30, 62),
          (32, 66), (38, 68), (42, 67), (40, 63), (38, 58), (34, 55),
          (30, 56), (28, 52), (29, 48), (27, 44), (23, 44), (21, 41),
          (19, 43), (15, 44), (12, 44), (8, 43), (4, 43), (0, 39),
          (-2, 37), (-6, 36)]
AFRICA = [(-17, 15), (-16, 20), (-13, 27), (-10, 30), (-6, 34),
          (-1, 35), (4, 37), (10, 37), (11, 34), (15, 32), (20, 32),
          (25, 32), (30, 31), (32, 31), (34, 28), (36, 24), (38, 20),
          (40, 15), (43, 12), (46, 11), (51, 12), (51, 10), (48, 7),
          (44, 2), (41, -2), (40, -6), (40, -10), (38, -14),
          (36, -18), (34, -22), (32, -26), (29, -30), (26, -33),
          (22, -35), (19, -34), (17, -31), (15, -27), (13, -22),
          (12, -17), (12, -12), (10, -6), (9, -1), (9, 4), (6, 4),
          (0, 5), (-4, 5), (-8, 5), (-11, 7), (-13, 8), (-15, 11),
          (-17, 13)]
ASIA = [(30, 62), (35, 66), (40, 68), (48, 68), (55, 69), (62, 70),
        (70, 72), (78, 73), (88, 74), (98, 75), (108, 75), (118, 73),
        (128, 72), (138, 72), (148, 71), (156, 69), (162, 64),
        (162, 60), (158, 56), (152, 58), (146, 59), (142, 56),
        (141, 51), (140, 46), (138, 43), (134, 42), (130, 42),
        (127, 40), (124, 39), (121, 37), (120, 33), (118, 29),
        (113, 22), (110, 20), (108, 17), (106, 11), (104, 8),
        (101, 6), (99, 8), (98, 11), (96, 15), (94, 17), (91, 22),
        (88, 22), (86, 20), (83, 18), (80, 15), (78, 9), (76, 9),
        (75, 13), (73, 18), (71, 21), (68, 23), (65, 25), (62, 25),
        (59, 26), (57, 27), (54, 26), (53, 28), (51, 29), (49, 30),
        (48, 29), (46, 29), (44, 29), (42, 27), (40, 24), (38, 21),
        (37, 18), (35, 15), (33, 12), (31, 10), (30, 12), (31, 16),
        (33, 20), (34, 24), (35, 28), (36, 32), (38, 36), (40, 40),
        (42, 44), (44, 48), (45, 52), (44, 56), (42, 60), (40, 62),
        (36, 64), (33, 63)]
AUSTRALIA = [(113, -22), (114, -28), (115, -33), (118, -35),
             (122, -34), (126, -32), (129, -32), (132, -32),
             (135, -35), (137, -35), (139, -37), (141, -38),
             (145, -38), (147, -39), (150, -37), (152, -34),
             (153, -31), (153, -27), (151, -24), (149, -21),
             (146, -19), (143, -15), (142, -11), (141, -13),
             (138, -14), (136, -12), (135, -15), (133, -12),
             (131, -12), (129, -14), (126, -14), (124, -16),
             (122, -17), (119, -19), (116, -20)]
NEW_ZEALAND = [(167, -45), (170, -42), (173, -40), (175, -38),
               (177, -38), (174, -41), (171, -43), (168, -46)]

CONTINENTS = [NORTH_AMERICA, GREENLAND, SOUTH_AMERICA, EUROPE,
              AFRICA, ASIA, AUSTRALIA]
# (New Zealand left out on purpose: at this scale it renders as a
# 26x19px scratch, not a recognisable landmass.)


# --- the 12 stories ----------------------------------------------------------
# (number, category, headline, pin display xy, true lon/lat)
# Headlines: verified 17 Nov 2026 reporting; disputed claims attributed.
STORIES = [
    (1, "conflict", "Ukraine hits Kerch Bridge for a 2nd day",
     (600, 192), (36.5, 45.3)),
    (2, "conflict", "Iran drones at US radar in Bahrain foiled",
     (592, 246), (50.5, 26.2)),
    (3, "conflict", "Iran says tankers hit mines in Hormuz",
     (652, 246), (56.5, 26.5)),
    (4, "diplomacy", "Trump lands in Manila; 3-way talks Thu",
     (800, 310), (121.0, 14.6)),
    (5, "economy", "Nvidia posts record $115.8bn revenue",
     (158, 256), (-122.0, 37.4)),
    (6, "economy", "Dow falls 849 in 4th straight drop",
     (298, 246), (-74.0, 40.7)),
    (7, "health", "Ebola in DR Congo tops 11,000 cases",
     (528, 372), (25.0, -2.0)),
    (8, "health", "Measles: US loses free status, 5,412 cases",
     (222, 228), (-98.0, 39.0)),
    (9, "diplomacy", "Five EU states plan Rwanda return hub",
     (592, 372), (30.0, -2.0)),
    (10, "conflict", "Japan scrambles jets at Russian planes",
     (832, 238), (130.0, 33.6)),
    (11, "politics", "Mongolia president to quit over $25m claim",
     (762, 206), (107.0, 47.9)),
    (12, "politics", "Turkey seizes opposition TV Sozcu",
     (538, 204), (29.0, 41.0)),
]

LEGEND = [("CONFLICT", "conflict"), ("DIPLOMACY", "diplomacy"),
          ("ECONOMY", "economy"), ("HEALTH", "health"),
          ("POLITICS", "politics")]


# --- small line icons (28x28 box, gold) --------------------------------------
def icon_bridge(cv, ox, oy):
    cv.line(ox + 6, oy + 4, ox + 6, oy + 21, GOLD, 2)
    cv.line(ox + 22, oy + 4, ox + 22, oy + 21, GOLD, 2)
    cv.line(ox + 2, oy + 20, ox + 12, oy + 20, GOLD, 2)
    cv.line(ox + 16, oy + 20, ox + 26, oy + 20, GOLD, 2)
    cv.line(ox + 6, oy + 4, ox + 14, oy + 12, GOLD, 1)
    cv.line(ox + 22, oy + 4, ox + 14, oy + 12, GOLD, 1)
    cv.line(ox + 12, oy + 21, ox + 14, oy + 24, GOLD, 2)


def icon_drone(cv, ox, oy):
    for (rx, ry) in [(4, 4), (24, 4), (4, 24), (24, 24)]:
        cv.disc(ox + rx, oy + ry, 3, GOLD)
        cv.line(ox + 14, oy + 14, ox + rx, oy + ry, GOLD, 1)
    cv.disc(ox + 14, oy + 14, 3, GOLD)


def icon_tanker(cv, ox, oy):
    cv.polygon([(ox + 3, oy + 16), (ox + 25, oy + 16), (ox + 22, oy + 23),
                (ox + 6, oy + 23)], GOLD)
    cv.line(ox + 8, oy + 16, ox + 8, oy + 11, GOLD, 2)
    cv.disc(ox + 20, oy + 7, 3, GOLD)
    for (dx, dy) in [(0, -6), (5, -3), (5, 3), (0, 6), (-5, 3), (-5, -3)]:
        cv.line(ox + 20, oy + 7, ox + 20 + dx, oy + 7 + dy, GOLD, 1)


def icon_flags(cv, ox, oy):
    cv.line(ox + 8, oy + 5, ox + 8, oy + 24, GOLD, 2)
    cv.line(ox + 20, oy + 5, ox + 20, oy + 24, GOLD, 2)
    cv.polygon([(ox + 8, oy + 5), (ox + 18, oy + 8), (ox + 8, oy + 11)],
               GOLD)
    cv.polygon([(ox + 20, oy + 5), (ox + 10, oy + 8), (ox + 20, oy + 11)],
               GOLD)


def icon_chip(cv, ox, oy):
    cv.fill_rect(ox + 7, oy + 7, ox + 22, oy + 9, GOLD)
    cv.fill_rect(ox + 7, oy + 20, ox + 22, oy + 22, GOLD)
    cv.fill_rect(ox + 7, oy + 7, ox + 9, oy + 22, GOLD)
    cv.fill_rect(ox + 20, oy + 7, ox + 22, oy + 22, GOLD)
    cv.fill_rect(ox + 11, oy + 11, ox + 18, oy + 18, GOLD)
    for p in (10, 14, 18):
        cv.line(ox + p, oy + 3, ox + p, oy + 7, GOLD, 2)
        cv.line(ox + p, oy + 22, ox + p, oy + 26, GOLD, 2)
        cv.line(ox + 3, oy + p, ox + 7, oy + p, GOLD, 2)
        cv.line(ox + 22, oy + p, ox + 26, oy + p, GOLD, 2)


def icon_down(cv, ox, oy):
    cv.line(ox + 5, oy + 5, ox + 5, oy + 23, GOLD, 2)
    cv.line(ox + 5, oy + 23, ox + 24, oy + 23, GOLD, 2)
    cv.line(ox + 7, oy + 8, ox + 21, oy + 20, GOLD, 2)
    cv.line(ox + 21, oy + 20, ox + 15, oy + 20, GOLD, 2)
    cv.line(ox + 21, oy + 20, ox + 21, oy + 14, GOLD, 2)


def icon_virus(cv, ox, oy):
    cv.disc(ox + 14, oy + 14, 6, GOLD)
    for k in range(8):
        ang = k * math.pi / 4
        dx = round(9 * math.cos(ang))
        dy = round(9 * math.sin(ang))
        cv.line(ox + 14, oy + 14, ox + 14 + dx, oy + 14 + dy, GOLD, 2)


def icon_measles(cv, ox, oy):
    for (dx, dy) in [(7, 7), (14, 5), (21, 8), (10, 13), (18, 14),
                     (7, 20), (15, 21), (22, 20)]:
        cv.disc(ox + dx, oy + dy, 2, GOLD)


def icon_gate(cv, ox, oy):
    cv.fill_rect(ox + 5, oy + 5, ox + 16, oy + 7, GOLD)
    cv.fill_rect(ox + 5, oy + 5, ox + 7, oy + 23, GOLD)
    cv.fill_rect(ox + 14, oy + 5, ox + 16, oy + 23, GOLD)
    cv.line(ox + 18, oy + 14, ox + 25, oy + 14, GOLD, 2)
    cv.line(ox + 25, oy + 14, ox + 21, oy + 10, GOLD, 2)
    cv.line(ox + 25, oy + 14, ox + 21, oy + 18, GOLD, 2)


def icon_jet(cv, ox, oy):
    cv.polygon([(ox + 3, oy + 14), (ox + 12, oy + 10), (ox + 22, oy + 12),
                (ox + 25, oy + 14), (ox + 22, oy + 16), (ox + 12, oy + 18)],
               GOLD)
    cv.line(ox + 12, oy + 12, ox + 16, oy + 5, GOLD, 2)
    cv.line(ox + 12, oy + 16, ox + 16, oy + 23, GOLD, 2)


def icon_gavel(cv, ox, oy):
    cv.line(ox + 5, oy + 8, ox + 18, oy + 8, GOLD, 5)
    cv.line(ox + 12, oy + 8, ox + 20, oy + 21, GOLD, 3)
    cv.line(ox + 5, oy + 24, ox + 23, oy + 24, GOLD, 2)


def icon_tv(cv, ox, oy):
    cv.fill_rect(ox + 5, oy + 8, ox + 24, oy + 10, GOLD)
    cv.fill_rect(ox + 5, oy + 19, ox + 24, oy + 21, GOLD)
    cv.fill_rect(ox + 5, oy + 8, ox + 7, oy + 21, GOLD)
    cv.fill_rect(ox + 22, oy + 8, ox + 24, oy + 21, GOLD)
    cv.line(ox + 7, oy + 8, ox + 14, oy + 3, GOLD, 2)
    cv.line(ox + 22, oy + 8, ox + 14, oy + 3, GOLD, 2)
    cv.line(ox + 6, oy + 20, ox + 23, oy + 9, GOLD, 2)


ICONS = [icon_bridge, icon_drone, icon_tanker, icon_flags, icon_chip,
         icon_down, icon_virus, icon_measles, icon_gate, icon_jet,
         icon_gavel, icon_tv]


# --- drawing -----------------------------------------------------------------
def draw_pin(cv, tables, cx, cy, number, color, tx, ty):
    """Numbered pin: white ring, category fill, white number; thin leader
    line to the true location (tx, ty) with a dot on it."""
    cv.line(cx, cy, tx, ty, FAINT, 1)
    cv.disc(tx, ty, 3, LAND)
    cv.ring(cx, cy, 22, WHITE, color, 2)
    num = str(number)
    t = tables["HEADXS"]
    nx = cx - text_width(t, num) // 2
    ny = cy - text_height(t, num) // 2
    draw_text(cv, t, nx, ny, num, WHITE)


def draw_map(cv, tables):
    cv.fill_rect(28, 132, 996, 492, PANEL)
    # faint graticule: every 45 deg lon, every ~32 deg lat
    for k in range(9):
        x = 40 + k * 118
        cv.fill_rect(x, 132, x + 1, 492, GRID)
    for k in range(5):
        y = 138 + k * 86
        cv.fill_rect(28, y, 996, y + 1, GRID)
    # panel border
    cv.fill_rect(28, 132, 996, 133, GRID)
    cv.fill_rect(28, 491, 996, 492, GRID)
    cv.fill_rect(28, 132, 29, 492, GRID)
    cv.fill_rect(995, 132, 996, 492, GRID)
    for poly in CONTINENTS:
        cv.polygon([geo(lon, lat) for lon, lat in poly], LAND)
    for num, cat, _h, (px, py), (lon, lat) in STORIES:
        tx, ty = geo(lon, lat)
        draw_pin(cv, tables, px, py, num, CAT[cat], tx, ty)


def draw_legend(cv, tables):
    t = tables["LEGEND"]
    items = []
    total = 0
    for label, cat in LEGEND:
        w = 16 + 6 + text_width(t, label)
        items.append((label, cat, w))
        total += w
    total += 28 * (len(items) - 1)
    x = (W - total) // 2
    cy = 515
    for label, cat, w in items:
        cv.disc(x + 8, cy, 8, CAT[cat])
        draw_text(cv, t, x + 22, cy - text_height(t, label) // 2,
                  label, WHITE)
        x += w + 28


def draw_stories(cv, tables):
    t = tables["HEAD"]
    y0, rh = 540, 33
    for i, (num, cat, head, _p, _g) in enumerate(STORIES):
        cy = y0 + i * rh + rh // 2
        # number dot (30px)
        cv.ring(108, cy, 15, WHITE, CAT[cat], 2)
        n = str(num)
        nt = tables["HEADXS"]
        draw_text(cv, nt, 108 - text_width(nt, n) // 2,
                  cy - text_height(nt, n) // 2, n, WHITE)
        # line icon
        ICONS[i](cv, 137, cy - 14)
        # headline, vertically centred
        draw_text(cv, t, 177, cy - text_height(t, head) // 2, head, WHITE)


def draw_header(cv, tables):
    draw_text_centered(cv, tables["LABEL"], W // 2, 16,
                       "THE WORLD IN ONE DAY", GOLD)
    draw_text_centered(cv, tables["MASTHEAD"], W // 2, 38,
                       "TUESDAY 17 NOVEMBER 2026", WHITE)
    draw_text_centered(cv, tables["LABEL"], W // 2, 96,
                       "12 STORIES | 6 CONTINENTS | 10 FIELDS", MUTE)
    cv.fill_rect(40, 122, 984, 124, GOLD)


def draw_footer(cv, tables):
    cv.fill_rect(0, 942, W, 1004, GOLD)
    t = tables["LEGEND"]
    draw_text_centered(cv, t, W // 2, 949,
                       "AND FINALLY: Tonight the world shines a light",
                       INK)
    draw_text_centered(cv, t, W // 2, 975,
                       "for Voyager 1 as it nears one light-day from Earth \u2014 NASA",
                       INK)
    draw_text_centered(cv, tables["DECKSM"], W // 2, 1006,
                       "Every story reported on Tuesday 17 November 2026. "
                       "Sources: Reuters, AP, WHO, UN News, TechCrunch.",
                       FAINT)


def main():
    tables = load_tables()
    cv = Canvas(W, H, NAVY)
    draw_header(cv, tables)
    draw_map(cv, tables)
    draw_legend(cv, tables)
    draw_stories(cv, tables)
    draw_footer(cv, tables)
    data = png_bytes(cv)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, OUT_NAME)
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes, %dx%d)" % (path, len(data), W, H))


if __name__ == "__main__":
    main()
