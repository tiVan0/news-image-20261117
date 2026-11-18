#!/usr/bin/env python3
"""Kind Forge — news-image-20261117, iteration v3.

Draws a 1024x1024 newspaper front page for Tuesday 17 November 2026:
3 illustrated leads, 12 numbered cards (4x3 grid), a soft world map,
a 27-item ALSO list, and a gold Voyager strip — 43 stories in total.

Pure Python 3 standard library at runtime (no PIL, no network).
Reads bitmap glyph tables from font_tables.json (generated at build
time by gen_fonts.py) and writes a deterministic PNG.

Usage:  MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png
        python3 main.py                          # writes ./entry.png
"""
import json
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
NAVY = (13, 27, 62)
NAVY2 = (18, 36, 78)
CREAM = (245, 240, 230)
CREAM2 = (239, 230, 208)
GOLD = (201, 162, 39)
GOLD_DK = (176, 138, 28)
WHITE = (255, 255, 255)
INK = (24, 24, 24)
GREY = (90, 88, 80)
FRAME = (216, 210, 196)
SEA = (207, 224, 234)
LAND = (239, 230, 208)
BAND_BG = {
    "blue": (214, 228, 240), "red": (244, 214, 210), "teal": (205, 232, 226),
    "green": (214, 234, 210), "orange": (250, 226, 196), "purple": (228, 216, 240),
    "grey": (228, 226, 220),
}
KICKER = {
    "EUROPE": (31, 76, 141), "MIDDLE EAST": (178, 34, 34),
    "ASIA": (15, 120, 110), "AMERICA": (34, 110, 60),
    "AFRICA": (204, 110, 20), "LATIN AMERICA": (110, 70, 160),
    "GLOBAL": (70, 70, 70),
}

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg * (w * h))

    def _i(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._i(x, y)
            self.px[i:i + 3] = bytes(c)

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = self._i(x0, yy)
            self.px[i:i + len(row)] = row

    def frame(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def hline(self, x0, x1, y, c, t=1):
        self.rect(min(x0, x1), y, abs(x1 - x0) + 1, t, c)

    def vline(self, x, y0, y1, c, t=1):
        self.rect(x, min(y0, y1), t, abs(y1 - y0) + 1, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            self.rect(x - t // 2, y - t // 2, t, t, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, c, fill=True):
        if fill:
            for yy in range(cy - r, cy + r + 1):
                dx = int((r * r - (yy - cy) ** 2) ** 0.5) if abs(yy - cy) <= r else 0
                self.rect(cx - dx, yy, 2 * dx + 1, 1, c)
        else:
            import math
            for a in range(360):
                rad = a * math.pi / 180.0
                self.set(int(cx + r * math.cos(rad)), int(cy + r * math.sin(rad)), c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            t = 1.0 - ((yy - cy) / ry) ** 2
            dx = int(rx * (t ** 0.5)) if t > 0 else 0
            self.rect(cx - dx, yy, 2 * dx + 1, 1, c)

    def poly(self, pts, c):
        """Scanline polygon fill (pts: list of (x, y))."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                self.rect(int(xs[j]), y, int(xs[j + 1]) - int(xs[j]) + 1, 1, c)

    def ring(self, cx, cy, r0, r1, c):
        for yy in range(cy - r1, cy + r1 + 1):
            for xx in range(cx - r1, cx + r1 + 1):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if r0 * r0 <= d2 <= r1 * r1:
                    self.set(xx, yy, c)

# ---------------------------------------------------------------- fonts
TABLES = None


def load_tables():
    global TABLES
    if TABLES is None:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "font_tables.json"), encoding="utf-8") as f:
            TABLES = json.load(f)
    return TABLES


def text_w(text, table):
    t = load_tables()[table]
    return sum(t.get(ch, t[" "])["adv"] for ch in text)


def draw_text(cv, x, baseline_y, text, table, color):
    t = load_tables()[table]
    cx = x
    for ch in text:
        g = t.get(ch)
        if g is None:
            g = t[" "]
        if g["w"] and g["h"]:
            raw = bytes.fromhex(g["hex"])
            rb = (g["w"] + 7) // 8
            gx = cx + g["xoff"]
            gy = baseline_y + g["yoff"]
            for yy in range(g["h"]):
                row = raw[yy * rb:(yy + 1) * rb]
                for xx in range(g["w"]):
                    if row[xx // 8] >> (7 - xx % 8) & 1:
                        cv.set(gx + xx, gy + yy, color)
        cx += g["adv"]
    return cx


def wrap(text, table, max_w):
    """Greedy word wrap; returns list of lines (never splits a word)."""
    words = text.split(" ")
    lines, cur = [], ""
    for wd in words:
        cand = wd if not cur else cur + " " + wd
        if text_w(cand, table) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_lines(text, table, max_w, max_lines):
    """Wrap; if it overflows max_lines, drop trailing words with ellipsis."""
    lines = wrap(text, table, max_w)
    if len(lines) <= max_lines:
        return lines
    out = lines[:max_lines]
    while text_w(out[-1] + " …", table) > max_w and len(out[-1]) > 1:
        out[-1] = out[-1].rsplit(" ", 1)[0] if " " in out[-1] else out[-1][:-1]
    out[-1] = out[-1] + " …"
    return out

# ---------------------------------------------------------------- PNG
def write_png(cv, path):
    raw = b"".join(b"\x00" + bytes(cv.px[y * cv.w * 3:(y + 1) * cv.w * 3])
                   for y in range(cv.h))
    comp = zlib.compress(raw, 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ---------------------------------------------------------------- data
LEADS = [
    {"n": 1, "region": "EUROPE", "field": "UKRAINE WAR", "band": "blue",
     "headline": "Ukraine hits Kerch bridge for second day; road span falls into strait",
     "deck": "Two killed; traffic halts; Kyiv bridges hit in reply.",
     "scene": "kerch"},
    {"n": 2, "region": "MIDDLE EAST", "field": "ENERGY", "band": "red",
     "headline": "Iran says four tankers hit mines in Strait of Hormuz",
     "deck": "UKMTO confirms one tanker hit; claims unverified.",
     "scene": "hormuz"},
    {"n": 3, "region": "ASIA", "field": "DIPLOMACY", "band": "teal",
     "headline": "Trump lands in Manila; first Trump–Xi–Putin meeting set for Thursday",
     "deck": "ASEAN summit; Quad meets again.",
     "scene": "manila"},
]

CARDS = [
    {"n": 4, "region": "MIDDLE EAST", "field": "US–IRAN", "band": "red",
     "headline": "Iran says drones hit US radar in Bahrain; US says all intercepted",
     "deck": "Bahrain, CENTCOM report no damage.",
     "scene": "radar"},
    {"n": 5, "region": "AMERICA", "field": "TECH", "band": "green",
     "headline": "Nvidia posts record $115.8bn revenue as AI spending holds",
     "deck": "Data centre $107.6bn; post-Huang first.",
     "scene": "chip"},
    {"n": 6, "region": "AMERICA", "field": "MARKETS", "band": "red",
     "headline": "Dow falls 849 points in fourth straight drop",
     "deck": "Software shares lead slide; S&P −1.03%.",
     "scene": "down"},
    {"n": 7, "region": "AMERICA", "field": "FINANCE", "band": "blue",
     "headline": "JPMorgan software bug disrupts online banking and Zelle",
     "deck": "Not a cyberattack; restored Monday.",
     "scene": "bank"},
    {"n": 8, "region": "AMERICA", "field": "SPACE", "band": "purple",
     "headline": "Vulcan rocket fails minutes after liftoff; 40 Amazon satellites lost",
     "deck": "Kuiper satellites fail to reach orbit.",
     "scene": "rocket"},
    {"n": 9, "region": "AFRICA", "field": "HEALTH", "band": "orange",
     "headline": "Ebola cases in DR Congo double to 11,000 in three months",
     "deck": "5,400 deaths across 67 health zones.",
     "scene": "virus"},
    {"n": 10, "region": "AMERICA", "field": "HEALTH", "band": "orange",
     "headline": "US loses measles-free status after 5,412 cases in 2026",
     "deck": "Highest since 1991; 13 congenital cases.",
     "scene": "measles"},
    {"n": 11, "region": "EUROPE", "field": "MIGRATION", "band": "blue",
     "headline": "Five EU states plan Rwanda hub for rejected asylum seekers",
     "deck": "First transfers targeted for 2027.",
     "scene": "plane"},
    {"n": 12, "region": "ASIA", "field": "DEFENCE", "band": "grey",
     "headline": "Japan scrambles jets as Russian planes enter its airspace",
     "deck": "First intrusion since Sept 2024.",
     "scene": "jet"},
    {"n": 13, "region": "ASIA", "field": "POLITICS", "band": "teal",
     "headline": "Mongolia's president to resign over $25m accusation",
     "deck": "Denies claim; parliament must approve.",
     "scene": "parliament"},
    {"n": 14, "region": "EUROPE", "field": "PRESS FREEDOM", "band": "purple",
     "headline": "Turkey raids opposition TV Sözcü and halts broadcast",
     "deck": "Four detained; 6th outlet under trustees.",
     "scene": "tv"},
    {"n": 15, "region": "MIDDLE EAST", "field": "CEASEFIRE", "band": "orange",
     "headline": "Gaza truce frays: four killed Tuesday, medics say",
     "deck": "Rains wreck shelters; 1,600+ dead.",
     "scene": "tent"},
]

# ALSO items 16-42: "NN. Place: short summary" — summaries trimmed so
# each line fits one 283px column at 11px (verified by check_fit below).
ALSO = [
    (16, "COP31", "draft split on fossil fuels"),
    (17, "Pentagon", "fails ninth straight audit"),
    (18, "France", "146,000 march in strike"),
    (19, "Greece", "Iran-linked plot uncovered"),
    (20, "Chip curbs", "US tightens AI-chip access"),
    (21, "AI", "China trains on US rivals' output"),
    (22, "NICER", "NASA ends telescope science"),
    (23, "Leonids", "meteor shower peaks tonight"),
    (24, "Earthshot", "five winners get £1m each"),
    (25, "S. Africa", "17 killed in two shootings"),
    (26, "Knesset", "Kahana elected speaker"),
    (27, "Yemen", "Houthis advance on Aden"),
    (28, "Brazil", "thrash Singapore 7–0"),
    (29, "Norway", "Haaland's late penalty wins it"),
    (30, "Uttarakhand", "bus plunges; eight killed"),
    (31, "Fed", "Cook lawyer threatens boycott"),
    (32, "Tech outages", "follow Trump on Asia tour"),
    (33, "Chernobyl", "regulators warn nuclear risk"),
    (34, "Drones", "Russia says 1,441 downed"),
    (35, "Serbia", "Student List sworn in"),
    (36, "An-12", "Russia says 19 killed in crash"),
    (37, "Canada–China", "Beijing cuts tariffs"),
    (38, "Akvan", "forecast to strike India Friday"),
    (39, "Mozambique", "Mondlane denies charges"),
    (40, "West Bank", "woman, 72, shot dead"),
    (41, "Moldova", "airspace shut after drone"),
    (42, "Pope", "Mass for 1.5m closes Lima tour"),
]

VOYAGER = ("AND FINALLY — Voyager 1 nears one light-day from Earth tonight; "
           "NASA asks the world to shine a light skyward.")

# ---------------------------------------------------------------- scenes
# Each scene draws inside band rect (x, y, w, h). Bold geometric shapes,
# no text except the TV "OFF AIR" label (drawn with the bitmap font).

def _sky(cv, x, y, w, h, c):
    cv.rect(x, y, w, h, c)


def scene_kerch(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (168, 198, 222))
    cv.rect(x, y + h - 22, w, 22, (96, 138, 172))          # strait
    cv.rect(x, y + h - 26, w, 4, (70, 110, 150))
    # bridge deck, left span standing, right span collapsed into water
    cv.rect(x + 8, y + 28, 150, 7, (60, 60, 66))
    cv.line(x + 8, y + 28, x + 158, y + 28, (60, 60, 66), 2)
    cv.line(x + 170, y + 34, x + 235, y + h - 24, (60, 60, 66), 5)  # fallen span
    cv.line(x + 235, y + h - 24, x + 300, y + h - 24, (60, 60, 66), 4)
    for px in (30, 80, 130):                                # pylons
        cv.vline(x + px, y + 6, y + 28, (60, 60, 66), 4)
    for px in (30, 80, 130):                                # cables
        cv.line(x + px, y + 6, x + px - 22, y + 28, (90, 90, 96), 1)
        cv.line(x + px, y + 6, x + px + 22, y + 28, (90, 90, 96), 1)
    for (sx, sy, r) in ((185, 24, 11), (205, 16, 14), (228, 26, 9)):  # smoke
        cv.circle(x + sx, y + sy, r, (120, 120, 124))
        cv.circle(x + sx + 4, y + sy - 4, r - 4, (150, 150, 154))
    cv.circle(x + 200, y + 30, 6, (230, 90, 30))            # fire glow
    cv.circle(x + 200, y + 30, 3, (250, 200, 60))


def scene_hormuz(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (240, 200, 170))
    cv.rect(x, y + h - 26, w, 26, (52, 96, 138))            # sea
    cv.rect(x, y + h - 30, w, 4, (40, 80, 120))
    cv.rect(x + 40, y + h - 52, 230, 24, (40, 40, 44))      # tanker hull
    cv.rect(x + 60, y + h - 68, 60, 16, (200, 60, 40))      # deck house
    cv.rect(x + 230, y + h - 78, 8, 26, (40, 40, 44))       # funnel
    for (fx, fy, r) in ((150, 30, 14), (180, 26, 18), (215, 32, 12)):  # flames
        cv.poly([(x + fx - r, y + fy + r), (x + fx, y + fy - r - 6),
                 (x + fx + r, y + fy + r)], (240, 120, 20))
        cv.poly([(x + fx - r // 2, y + fy + r // 2), (x + fx, y + fy - r),
                 (x + fx + r // 2, y + fy + r // 2)], (250, 200, 40))
    for (sx, sy, r) in ((150, 14, 10), (185, 12, 11), (215, 16, 9)):
        cv.circle(x + sx, y + sy, r, (90, 90, 92))
    cv.circle(x + 285, y + 18, 7, (255, 255, 255))          # sun
    cv.circle(x + 285, y + 18, 4, (250, 210, 90))


def scene_manila(cv, x, y, w, h):
    _sky(cv, x, y, w, h, (196, 216, 238))
    # three flags on poles, left to right: US, China, Russia
    flags = [((210, 60, 60), (255, 255, 255)), ((200, 40, 40), (250, 220, 60)),
             ((255, 255, 255), (200, 40, 40))]
    for i, (c1, c2) in enumerate(flags):
        fx = x + 28 + i * 100
        cv.vline(fx, y + 14, y + 62, (70, 70, 74), 3)
        cv.rect(fx, y + 16, 62, 20, c1)
        cv.rect(fx, y + 26, 62, 10, c2)
        cv.circle(fx + 31, y + 26, 4, (250, 220, 60))
    # plane above the flags
    px, py = x + w // 2, y + 62
    cv.poly([(px - 46, py), (px + 46, py + 2), (px - 46, py + 5)], (40, 40, 46))
    cv.poly([(px - 10, py - 12), (px + 8, py - 12), (px + 2, py)], (40, 40, 46))
    cv.poly([(px + 30, py - 8), (px + 44, py - 2), (px + 30, py + 2)], (40, 40, 46))
    cv.rect(x, y + h - 8, w, 8, (120, 160, 110))            # ground strip


def _band_bg(cv, x, y, w, h, key):
    cv.rect(x, y, w, h, BAND_BG[key])


def scene_radar(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "red")
    cx, cy = x + w // 2 - 40, y + 19
    cv.ring(cx, cy, 8, 10, (178, 34, 34))
    cv.ring(cx, cy, 16, 18, (178, 34, 34))
    cv.line(cx, cy, cx + 13, cy - 13, (178, 34, 34), 2)
    cv.circle(cx, cy, 4, (178, 34, 34))
    dx, dy = x + w - 52, y + 14                       # drone
    cv.circle(dx, dy, 4, (40, 40, 44))
    cv.rect(dx - 14, dy - 8, 28, 3, (40, 40, 44))
    cv.rect(dx - 14, dy + 5, 28, 3, (40, 40, 44))
    cv.vline(dx - 12, dy - 6, dy + 6, (40, 40, 44), 2)
    cv.vline(dx + 12, dy - 6, dy + 6, (40, 40, 44), 2)


def scene_chip(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "green")
    cx, cy = x + 62, y + 20
    cv.rect(cx - 15, cy - 13, 30, 26, (24, 90, 50))
    cv.rect(cx - 7, cy - 6, 14, 12, (120, 200, 140))
    for dx in (-15, 0, 15):
        cv.rect(cx + dx - 2, cy - 19, 4, 6, (24, 90, 50))
        cv.rect(cx + dx - 2, cy + 13, 4, 6, (24, 90, 50))
    for dy in (-13, 0, 13):
        cv.rect(cx - 21, cy + dy - 2, 6, 4, (24, 90, 50))
        cv.rect(cx + 15, cy + dy - 2, 6, 4, (24, 90, 50))
    pts = [(x + 120, y + 40), (x + 150, y + 30), (x + 175, y + 34),
           (x + 205, y + 16), (x + 232, y + 8)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], (24, 130, 60), 3)
    for (px, py) in pts:
        cv.circle(px, py, 3, (24, 130, 60))


def scene_down(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "red")
    pts = [(x + 24, y + 8), (x + 70, y + 16), (x + 110, y + 12),
           (x + 160, y + 26), (x + 205, y + 38)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], (178, 34, 34), 3)
    for (px, py) in pts:
        cv.circle(px, py, 3, (178, 34, 34))
    cv.poly([(x + 205, y + 38), (x + 190, y + 36), (x + 200, y + 24)],
            (178, 34, 34))  # arrow head
    cv.rect(x + 14, y + 28, 10, 10, (178, 34, 34))
    cv.rect(x + 34, y + 22, 10, 16, (178, 34, 34))
    cv.rect(x + 54, y + 32, 10, 6, (178, 34, 34))


def scene_bank(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "blue")
    bx, by = x + 30, y + 2
    cv.poly([(bx, by + 6), (bx + 44, by), (bx + 88, by + 6)], (31, 76, 141))
    cv.rect(bx + 4, by + 8, 80, 22, (31, 76, 141))
    for i in range(4):
        cv.rect(bx + 10 + i * 20, by + 11, 8, 16, (220, 230, 240))
    cv.rect(bx, by + 28, 88, 4, (31, 76, 141))
    cv.rect(bx + 4, by + 32, 80, 3, (31, 76, 141))
    # bug: body + legs + antennae
    cx, cy = x + 178, y + 24
    cv.ellipse(cx, cy, 14, 9, (40, 40, 44))
    cv.circle(cx - 12, cy - 2, 5, (40, 40, 44))
    for s in (-1, 1):
        cv.line(cx - 12, cy - 6, cx - 20, cy - 8 * s, (40, 40, 44), 2)
        cv.line(cx - 4, cy + 8, cx - 10, cy + 14, (40, 40, 44), 2)
        cv.line(cx + 4, cy + 8, cx + 10, cy + 14, (40, 40, 44), 2)
        cv.line(cx + 12, cy - 2, cx + 20, cy - 6 * s, (40, 40, 44), 2)


def scene_rocket(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "purple")
    cx, cy = x + w // 2, y + 19
    cv.poly([(cx, cy - 18), (cx + 8, cy - 2), (cx + 8, cy + 10),
             (cx - 8, cy + 10), (cx - 8, cy - 2)], (200, 60, 40))
    cv.circle(cx, cy - 7, 4, (200, 230, 250))
    cv.poly([(cx - 8, cy + 10), (cx - 16, cy + 18), (cx - 8, cy + 15)], (200, 60, 40))
    cv.poly([(cx + 8, cy + 10), (cx + 16, cy + 18), (cx + 8, cy + 15)], (200, 60, 40))
    cv.poly([(cx - 5, cy + 12), (cx + 5, cy + 12), (cx, cy + 18)], (240, 140, 20))
    for (sx, sy, r) in ((x + 34, y + 12, 3), (x + 210, y + 10, 2),
                        (x + 44, y + 34, 2), (x + 196, y + 34, 3)):
        cv.circle(sx, sy, r, (255, 255, 255))


def _virus(cv, cx, cy, r, body, spike):
    for k in range(8):
        import math
        a = k * math.pi / 4
        cv.line(cx, cy, int(cx + (r + 5) * math.cos(a)),
                int(cy + (r + 5) * math.sin(a)), spike, 2)
        cv.circle(int(cx + (r + 5) * math.cos(a)),
                  int(cy + (r + 5) * math.sin(a)), 2, spike)
    cv.circle(cx, cy, r, body)
    cv.circle(cx - r // 3, cy - r // 3, r // 4, (255, 255, 255))


def scene_virus(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "orange")
    _virus(cv, x + 70, y + 19, 11, (190, 90, 20), (150, 60, 10))
    _virus(cv, x + 165, y + 17, 9, (210, 110, 30), (170, 70, 15))
    _virus(cv, x + 215, y + 21, 6, (220, 130, 50), (180, 80, 20))


def scene_measles(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "orange")
    _virus(cv, x + w // 2, y + 19, 13, (200, 50, 50), (160, 30, 30))
    for (sx, sy, r) in ((x + 40, y + 12, 5), (x + 200, y + 12, 4),
                        (x + 30, y + 34, 4), (x + 210, y + 34, 5)):
        cv.circle(sx, sy, r, (200, 50, 50))


def scene_plane(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "blue")
    px, py = x + 90, y + h // 2
    cv.poly([(px - 60, py), (px + 60, py + 2), (px - 60, py + 6)], (31, 76, 141))
    cv.poly([(px - 14, py - 14), (px + 10, py - 14), (px + 2, py)], (31, 76, 141))
    cv.poly([(px + 38, py - 10), (px + 56, py - 2), (px + 38, py + 2)], (31, 76, 141))
    # door / gate on the right
    cv.rect(x + 180, y + 6, 34, 30, (90, 90, 96))
    cv.rect(x + 184, y + 9, 26, 24, (245, 240, 230))
    cv.circle(x + 202, y + 21, 3, (90, 90, 96))


def scene_jet(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "grey")
    px, py = x + w // 2, y + h // 2
    cv.poly([(px - 70, py - 2), (px + 62, py), (px - 70, py + 4)], (50, 50, 56))
    cv.poly([(px - 20, py - 16), (px + 6, py - 16), (px - 4, py)], (50, 50, 56))
    cv.poly([(px - 30, py + 2), (px - 6, py + 14), (px + 2, py + 2)], (50, 50, 56))
    cv.poly([(px + 40, py - 8), (px + 58, py - 1), (px + 40, py + 2)], (50, 50, 56))
    cv.poly([(px - 70, py), (px - 84, py - 3), (px - 84, py + 3)], (240, 120, 20))
    for (sx, sy, r) in ((x + 26, y + 10, 3), (x + 210, y + 12, 2), (x + 40, y + 34, 2)):
        cv.circle(sx, sy, r, (255, 255, 255))


def scene_parliament(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "teal")
    bx, by = x + 48, y + 5
    cv.poly([(bx, by + 6), (bx + 40, by), (bx + 80, by + 6)], (15, 120, 110))
    cv.rect(bx + 4, by + 8, 72, 22, (15, 120, 110))
    for i in range(4):
        cv.rect(bx + 10 + i * 18, by + 11, 7, 16, (220, 240, 235))
    cv.rect(bx, by + 30, 80, 3, (15, 120, 110))
    cv.vline(x + 196, y + 6, y + 36, (90, 90, 96), 3)       # flag pole
    cv.rect(x + 196, y + 8, 26, 14, (200, 40, 40))


def scene_tv(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "purple")
    tx, ty = x + 58, y + 4
    cv.rect(tx, ty, 130, 30, (30, 30, 34))
    cv.rect(tx + 4, ty + 4, 122, 22, (20, 20, 24))
    label = "OFF AIR"
    lw = text_w(label, "sans_bold_11")
    draw_text(cv, tx + (130 - lw) // 2, ty + 19, label, "sans_bold_11", (240, 60, 60))
    cv.rect(tx + 55, ty + 30, 20, 3, (30, 30, 34))
    cv.rect(tx + 40, ty + 33, 50, 2, (30, 30, 34))


def scene_tent(cv, x, y, w, h):
    _band_bg(cv, x, y, w, h, "orange")
    # intact tent left, collapsed tent right, rain slashes
    cv.poly([(x + 30, y + 38), (x + 62, y + 12), (x + 94, y + 38)], (150, 100, 60))
    cv.line(x + 62, y + 12, x + 62, y + 38, (120, 75, 40), 2)
    cv.poly([(x + 140, y + 38), (x + 168, y + 24), (x + 196, y + 38),
             (x + 182, y + 38), (x + 168, y + 32), (x + 154, y + 38)], (120, 80, 50))
    cv.line(x + 150, y + 38, x + 190, y + 38, (120, 80, 50), 3)
    for (rx, ry) in ((x + 110, y + 8), (x + 130, y + 16), (x + 210, y + 8),
                     (x + 224, y + 18), (x + 20, y + 10)):
        cv.line(rx, ry, rx - 3, ry + 8, (70, 110, 160), 2)


SCENES = {"kerch": scene_kerch, "hormuz": scene_hormuz, "manila": scene_manila,
          "radar": scene_radar, "chip": scene_chip, "down": scene_down,
          "bank": scene_bank, "rocket": scene_rocket, "virus": scene_virus,
          "measles": scene_measles, "plane": scene_plane, "jet": scene_jet,
          "parliament": scene_parliament, "tv": scene_tv, "tent": scene_tent}

# ---------------------------------------------------------------- map
# Rough stylised continents (x, y) inside a 420x150 box, origin (8, 740).
CONTINENTS = [
    # North America
    [(28, 28), (70, 8), (118, 12), (138, 30), (118, 46), (96, 42),
     (84, 62), (58, 66), (40, 52), (18, 44)],
    # South America
    [(96, 78), (122, 74), (140, 92), (132, 122), (112, 140), (100, 112), (88, 94)],
    # Europe
    [(196, 22), (232, 10), (258, 20), (252, 38), (228, 44), (206, 38), (192, 30)],
    # Africa
    [(200, 58), (238, 52), (262, 66), (256, 96), (232, 116), (210, 96), (196, 74)],
    # Asia
    [(268, 14), (330, 6), (392, 16), (404, 34), (372, 48), (340, 60),
     (312, 52), (288, 60), (272, 40)],
    # Oceania
    [(356, 108), (384, 102), (398, 116), (380, 128), (360, 122)],
]
# pins: (story no, x, y, region) in map-box coordinates
PINS = [
    (1, 252, 30, "EUROPE"), (2, 276, 62, "MIDDLE EAST"), (3, 292, 66, "MIDDLE EAST"),
    (4, 372, 58, "ASIA"), (5, 62, 44, "AMERICA"), (6, 78, 50, "AMERICA"),
    (7, 48, 54, "AMERICA"), (8, 96, 62, "AMERICA"), (9, 222, 88, "AFRICA"),
    (10, 88, 36, "AMERICA"), (11, 216, 34, "EUROPE"), (12, 396, 30, "ASIA"),
    (13, 330, 26, "ASIA"), (14, 262, 44, "MIDDLE EAST"), (15, 272, 52, "MIDDLE EAST"),
]


def draw_map(cv, mx, my, mw, mh):
    cv.rect(mx, my, mw, mh, SEA)
    cv.frame(mx, my, mw, mh, FRAME)
    for poly in CONTINENTS:
        cv.poly([(mx + px, my + py) for px, py in poly], LAND)
        for i in range(len(poly)):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % len(poly)]
            cv.line(mx + x0, my + y0, mx + x1, my + y1, (190, 175, 145), 1)
    for label, lx, ly in (("PACIFIC", 8, 96), ("ATLANTIC", 158, 96),
                          ("INDIAN", 336, 122)):
        draw_text(cv, mx + lx, my + ly, label, "sans_bold_10", (110, 140, 160))
    # Middle-East cluster: leader lines so pins 2/3/14/15 do not collide
    leaders = {2: (276, 62, 248, 88), 3: (292, 66, 312, 88),
               14: (262, 44, 236, 76), 15: (272, 52, 296, 106)}
    for n, px, py, region in PINS:
        if n in leaders:
            _, _, lx, ly = leaders[n]
            cv.line(mx + px, my + py, mx + lx, my + ly, (90, 90, 90), 1)
            px, py = lx, ly
        cv.circle(mx + px, my + py, 8, KICKER[region])
        cv.circle(mx + px, my + py, 8, KICKER[region])
        num = str(n)
        tw = text_w(num, "sans_bold_10")
        draw_text(cv, mx + px - tw // 2, my + py + 4, num, "sans_bold_10", WHITE)


# ---------------------------------------------------------------- layout
def draw_masthead(cv):
    cv.rect(0, 0, W, 145, NAVY)
    cv.rect(0, 141, W, 4, GOLD)
    draw_text(cv, 24, 34, "KIND FORGE", "sans_bold_20", GOLD)
    right = "ONE DAY, ONE PLANET"
    draw_text(cv, W - 24 - text_w(right, "sans_bold_13"), 32, right,
              "sans_bold_13", (200, 205, 220))
    date = "TUESDAY 17 NOVEMBER 2026"
    draw_text(cv, (W - text_w(date, "serif_bold_56")) // 2, 102, date,
              "serif_bold_56", WHITE)
    badge = "43 STORIES · 6 CONTINENTS · ONE DAY"
    draw_text(cv, (W - text_w(badge, "sans_bold_15")) // 2, 132, badge,
              "sans_bold_15", GOLD)


def draw_leads(cv):
    for i, lead in enumerate(LEADS):
        x = 8 + i * 338
        w = 330
        y = 145
        SCENES[lead["scene"]](cv, x, y, w, 72)
        cv.frame(x, y, w, 72, FRAME)
        kick = f"{lead['region']} · {lead['field']}"
        draw_text(cv, x, y + 90, kick, "sans_bold_13", KICKER[lead["region"]])
        lines = fit_lines(lead["headline"], "sans_bold_22", w, 3)
        by = y + 116
        for ln in lines:
            draw_text(cv, x, by, ln, "sans_bold_22", INK)
            by += 25
        draw_text(cv, x, y + 184, lead["deck"], "sans_12", GREY)


def draw_cards(cv):
    for idx, card in enumerate(CARDS):
        col, row = idx % 4, idx // 4
        x = 8 + col * 254
        y = 335 + row * 135
        w, h = 246, 129
        cv.rect(x, y, w, h, WHITE)
        cv.frame(x, y, w, h, FRAME)
        SCENES[card["scene"]](cv, x + 1, y + 1, w - 2, 38)
        kick = f"{card['region']} · {card['field']}"
        draw_text(cv, x + 6, y + 54, kick, "sans_bold_11", KICKER[card["region"]])
        lines = fit_lines(card["headline"], "sans_bold_16", w - 12, 3)
        by = y + 72
        for ln in lines:
            draw_text(cv, x + 6, by, ln, "sans_bold_16", INK)
            by += 18
        draw_text(cv, x + 6, y + 123, card["deck"], "sans_11", GREY)
        # story number tab
        cv.rect(x + w - 26, y + 39, 25, 15, NAVY)
        num = str(card["n"])
        draw_text(cv, x + w - 26 + (25 - text_w(num, "sans_bold_10")) // 2,
                  y + 51, num, "sans_bold_10", WHITE)


def draw_bottom(cv):
    y0 = 740
    # --- map + figures strip + legend (left)
    draw_map(cv, 8, y0, 420, 150)
    # figures strip: two lines — the full one-line text (642px at 12px)
    # cannot fit a 420px strip, so header and figures split across lines.
    strip_head = "THE DAY IN FOUR FIGURES"
    strip_figs = "2 days Kerch · 11,000+ Ebola · $115.8bn Nvidia · −849 Dow"
    cv.rect(8, 892, 420, 28, CREAM2)
    cv.frame(8, 892, 420, 28, FRAME)
    draw_text(cv, 8 + (420 - text_w(strip_head, "sans_bold_12")) // 2, 903,
              strip_head, "sans_bold_12", NAVY)
    draw_text(cv, 8 + (420 - text_w(strip_figs, "sans_bold_11")) // 2, 917,
              strip_figs, "sans_bold_11", NAVY)
    legend = "N. AMERICA · S. AMERICA · EUROPE · AFRICA · ASIA · OCEANIA · GLOBAL"
    draw_text(cv, 8 + (420 - text_w(legend, "sans_11")) // 2, 940,
              legend, "sans_11", GREY)
    # --- ALSO list (right)
    ax = 440
    draw_text(cv, ax, 760, "ALSO ON 16–42", "sans_bold_15", NAVY)
    cv.rect(ax, 766, 576, 2, GOLD)
    col_w = 283
    for i, (n, place, summ) in enumerate(ALSO):
        col = 0 if i < 14 else 1
        r = i % 14
        x = ax + col * (col_w + 10)
        by = 780 + (r * 25) // 2
        num = f"{n}."
        draw_text(cv, x, by, num, "sans_bold_11", GOLD_DK)
        nx = x + text_w(num, "sans_bold_11") + 4
        draw_text(cv, nx, by, f"{place}: {summ}", "sans_11", INK)


def draw_strip_footer(cv):
    cv.rect(0, 950, W, 38, GOLD)
    draw_text(cv, (W - text_w(VOYAGER, "sans_bold_15")) // 2, 975,
              VOYAGER, "sans_bold_15", NAVY)
    draw_text(cv, 8, 1004,
              "Every story happened or was first reported on Tuesday 17 November 2026. "
              "Disputed claims are attributed.", "sans_10", GREY)
    draw_text(cv, 8, 1018,
              "Sources: Reuters, AP, AFP, BBC, Al Jazeera, WHO, UN News, NASA, TechCrunch. "
              "Original drawings.", "sans_10", GREY)


def check_fit():
    """Fail loudly (stderr) if any text overflows its allotted box."""
    problems = []
    for lead in LEADS:
        if len(wrap(lead["headline"], "sans_bold_22", 330)) > 3:
            problems.append(f"lead {lead['n']} headline >3 lines")
        if text_w(lead["deck"], "sans_12") > 330:
            problems.append(f"lead {lead['n']} deck overflow")
    for card in CARDS:
        if len(wrap(card["headline"], "sans_bold_16", 234)) > 3:
            problems.append(f"card {card['n']} headline >3 lines")
        if text_w(card["deck"], "sans_11") > 234:
            problems.append(f"card {card['n']} deck overflow")
    for n, place, summ in ALSO:
        if text_w(f"{n}. {place}: {summ}", "sans_11") > 283:
            problems.append(f"ALSO {n} overflow: {place}: {summ}")
    if text_w(VOYAGER, "sans_bold_15") > 1008:
        problems.append("voyager strip overflow")
    if text_w("2 days Kerch · 11,000+ Ebola · $115.8bn Nvidia · −849 Dow",
              "sans_bold_11") > 420:
        problems.append("figures strip overflow")
    return problems


def build():
    cv = Canvas(W, H, CREAM)
    draw_masthead(cv)
    draw_leads(cv)
    draw_cards(cv)
    draw_bottom(cv)
    draw_strip_footer(cv)
    return cv


def main():
    problems = check_fit()
    for p in problems:
        print("FIT PROBLEM:", p, file=sys.stderr)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    size = write_png(build(), path)
    print(f"wrote {path} ({size} bytes)")
    if problems:
        sys.exit(2)


if __name__ == "__main__":
    main()
