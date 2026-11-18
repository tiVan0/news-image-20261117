#!/usr/bin/env python3
"""news-image-20261117 v2 -- "Latent Atlas" iterasi 1.

Draws a 1024x1024 newspaper front page summing up Tuesday 17 November
2026 in 34 verified stories: 3 illustrated leads, 12 numbered cards,
a dot-matrix world map with numbered pins, an ALSO list (16-33) and a
gold Voyager strip. Pure Python standard library only (json, math, os,
struct, zlib). Bitmap glyph tables are loaded from font_tables.json
next to this file (generated at build time with PIL; never at runtime).

Deterministic: two runs produce byte-identical PNGs.
"""
import json
import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---- palette ----
NAVY = (13, 27, 62)
CREAM = (245, 240, 230)
GOLD = (201, 162, 39)
GOLD_DK = (176, 138, 24)
CARD = (255, 255, 255)
FRAME = (216, 210, 196)
INK = (24, 30, 46)
MUTED = (90, 96, 112)
BLUE = (37, 99, 235)      # Europe
RED = (220, 38, 38)       # Middle East
TEAL = (13, 148, 136)     # Asia
GREEN = (21, 128, 61)     # America
ORANGE = (234, 88, 12)    # Africa
PURPLE = (124, 58, 237)   # Latin America
GREY = (71, 85, 105)      # Global
LAND = (74, 85, 104)
OCEAN_LBL = (124, 138, 160)

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "font_tables.json")) as f:
    FONTS = json.load(f)


# ---- canvas ----
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg) * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                self.px[i], self.px[i + 1], self.px[i + 2] = c
                i += 3

    def disc(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            for xx in range(cx - dx, cx + dx + 1):
                self.set(xx, cy + dy, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx, dy = x1 - x0, y1 - y0
        n = max(abs(dx), abs(dy), 1)
        r = t // 2
        for i in range(n + 1):
            x = x0 + round(dx * i / n)
            y = y0 + round(dy * i / n)
            if t <= 1:
                self.set(x, y, c)
            else:
                self.disc(x, y, r, c)

    def poly(self, pts, c):
        """Scanline fill of a polygon given as [(x, y), ...]."""
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
                for x in range(max(0, int(math.ceil(xs[j]))),
                               min(self.w, int(xs[j + 1]) + 1)):
                    self.set(x, y, c)

    def polyline(self, pts, c, t=1):
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], c, t)


# ---- text (bitmap glyphs; y is the cap-top of the text) ----
def text_w(table, s):
    g = FONTS[table]["glyphs"]
    return sum(g.get(str(ord(ch)), g["63"])["adv"] for ch in s)


def draw_text(cv, x, y, table, s, color):
    g = FONTS[table]["glyphs"]
    for ch in s:
        gl = g.get(str(ord(ch)), g["63"])
        w, h = gl["w"], gl["h"]
        if w and h:
            raw = bytes.fromhex(gl["hex"])
            bpr = (w + 7) // 8
            ox, oy = x + gl["dx"], y + gl["yoff"]
            for yy in range(h):
                for xx in range(w):
                    if raw[yy * bpr + xx // 8] >> (7 - (xx % 8)) & 1:
                        cv.set(ox + xx, oy + yy, color)
        x += gl["adv"]
    return x


def draw_centered(cv, cx, y, table, s, color):
    draw_text(cv, cx - text_w(table, s) // 2, y, table, s, color)


def draw_tracked(cv, x, y, table, s, color, track):
    for ch in s:
        if ch == " ":
            x += FONTS[table]["glyphs"]["32"]["adv"] + track
            continue
        x = draw_text(cv, x, y, table, ch, color) + track
    return x


def wrap_lines(table, s, maxw, maxlines):
    words = s.split(" ")
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_w(table, trial) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines[:maxlines]


# ---- content (line breaks pre-measured from the real glyph tables) ----
LEADS = [
    {"num": 1, "kicker": "EUROPE \u00b7 UKRAINE WAR", "color": BLUE,
     "band": (219, 231, 245), "icon": "bridge",
     "head": ["Ukraine hits Kerch bridge", "for second day; road",
              "span falls into strait"],
     "deck": ["Two killed as traffic halts; Russia strikes Kyiv bridges",
              "in reply."]},
    {"num": 2, "kicker": "MIDDLE EAST \u00b7 ENERGY", "color": RED,
     "band": (251, 227, 216), "icon": "tanker",
     "head": ["Iran says four tankers hit", "mines in Strait of Hormuz"],
     "deck": ["UKMTO confirms one tanker struck off Oman; claims",
              "unverified."]},
    {"num": 3, "kicker": "ASIA \u00b7 DIPLOMACY", "color": TEAL,
     "band": (216, 239, 232), "icon": "flags",
     "head": ["Trump lands in Manila;", "first Trump-Xi-Putin",
              "meeting set for Thursday"],
     "deck": ["ASEAN summit and first Quad meeting in two years;",
              "talks set for Shenzhen."]},
]

CARDS = [
    {"num": 4, "kicker": "MIDDLE EAST \u00b7 US-IRAN", "color": RED, "icon": "radar",
     "head": ["Iran says drones hit US", "radar in Bahrain; US says",
              "all intercepted"],
     "deck": ["Bahrain and CENTCOM report no damage or", "casualties."]},
    {"num": 5, "kicker": "AMERICA \u00b7 TECH", "color": GREEN, "icon": "chip",
     "head": ["Nvidia posts record", "$115.8bn revenue as AI", "spending holds"],
     "deck": ["Data centre $107.6bn; first report since", "Huang stepped down."]},
    {"num": 6, "kicker": "AMERICA \u00b7 MARKETS", "color": GREEN, "icon": "chartdown",
     "head": ["Dow falls 849 points in", "fourth straight drop"],
     "deck": ["S&P -1.03%, Nasdaq -0.74%; software and AI", "shares lead slide."]},
    {"num": 7, "kicker": "AMERICA \u00b7 FINANCE", "color": GREEN, "icon": "bankbug",
     "head": ["JPMorgan software bug", "disrupts online banking", "and Zelle"],
     "deck": ["Chase says not a cyberattack; services", "restored Monday night."]},
    {"num": 8, "kicker": "AMERICA \u00b7 SPACE", "color": GREEN, "icon": "rocket",
     "head": ["Vulcan rocket fails", "minutes after liftoff; 40",
              "Amazon satellites lost"],
     "deck": ["Kuiper satellites fail to reach orbit in ULA", "setback."]},
    {"num": 9, "kicker": "AFRICA \u00b7 HEALTH", "color": ORANGE, "icon": "virus",
     "head": ["Ebola cases in DR Congo", "double to 11,000 in three", "months"],
     "deck": ["5,400 deaths across 67 health zones; children",
              "over a quarter of cases."]},
    {"num": 10, "kicker": "AMERICA \u00b7 HEALTH", "color": GREEN, "icon": "virus",
     "head": ["US loses measles-free", "status after 5,412 cases", "in 2026"],
     "deck": ["Highest since 1991; 13 babies born with", "congenital measles."]},
    {"num": 11, "kicker": "EUROPE \u00b7 MIGRATION", "color": BLUE, "icon": "planedoor",
     "head": ["Five EU states plan", "Rwanda hub for rejected", "asylum seekers"],
     "deck": ["First transfers targeted for 2027; rights", "groups criticise plan."]},
    {"num": 12, "kicker": "ASIA \u00b7 DEFENCE", "color": TEAL, "icon": "jet",
     "head": ["Japan scrambles jets as", "Russian planes enter its", "airspace"],
     "deck": ["Two aircraft near Okinoshima; first such",
              "intrusion since September 2024."]},
    {"num": 13, "kicker": "ASIA \u00b7 POLITICS", "color": TEAL, "icon": "parliament",
     "head": ["Mongolia's president to", "resign over $25m", "accusation"],
     "deck": ["Khurelsukh denies the claim; parliament must", "approve the move."]},
    {"num": 14, "kicker": "EUROPE \u00b7 PRESS FREEDOM", "color": BLUE, "icon": "tv",
     "head": ["Turkey raids opposition", "TV S\u00f6zc\u00fc and halts", "broadcast"],
     "deck": ["Four executives detained; sixth outlet under",
              "trustees since 2022."]},
    {"num": 15, "kicker": "LATIN AMERICA \u00b7 FAITH", "color": PURPLE, "icon": "cross",
     "head": ["Pope Leo XIV closes tour", "with Mass for 1.5 million", "in Lima"],
     "deck": ["Rosary thrown from crowd hits his face; he", "forgives the thrower."]},
]

ALSO = [
    "16. COP31: Antalya draft split over fossil fuels",
    "17. Pentagon: Pentagon fails ninth straight audit",
    "18. France: 146,000 march in French public-sector strike",
    "19. Iran plot: Assassination plot uncovered in Greece",
    "20. Chip curbs: US tightens AI-chip access via Asia",
    "21. AI distillation: China trains AI on US rivals' output",
    "22. NICER: NASA ends NICER science after motor fault",
    "23. Leonids: Leonid meteor shower peaks Tuesday night",
    "24. Earthshot: Five winners get \u00a31m each in Mumbai",
    "25. South Africa: 17 killed in two mass shootings",
    "26. Knesset: Kahana elected speaker in blow to Netanyahu",
    "27. Yemen: Houthis near Aden; Saudi swaps commander",
    "28. Brazil: Brazil thrash Singapore 7-0; Vin\u00edcius hat-trick",
    "29. Nations League: Haaland penalty sends Norway through",
    "30. Uttarakhand: Bus plunges into gorge; eight killed",
    "31. Fed: Cook's lawyer threatens White House boycott",
    "32. Tech outages: US outages follow Trump on Asia tour",
    "33. Chernobyl warning: Regulators warn of nuclear risk",
]

STRIP = ("AND FINALLY \u2014 Voyager 1 nears one light-day from Earth "
         "tonight; NASA asks the world to shine a light skyward.")
FOOT1 = ("Every story happened or was first reported on Tuesday 17 November "
         "2026. Disputed claims are attributed.")
FOOT2 = ("Sources: Reuters, AP, AFP, BBC, Al Jazeera, WHO, UN News, NASA, "
         "TechCrunch. Original drawings.")


# ---- pictograms (all program-drawn; no text except the TV "OFF AIR") ----
def icon_bridge(cv, cx, cy, s, col):
    # collapsed bridge over a strait, with smoke
    u = s / 10.0
    cv.line(int(cx - 4 * u), int(cy + 2 * u), int(cx + 4 * u), int(cy + 2 * u), col, 2)
    cv.polyline([(int(cx - 4 * u), int(cy + 2 * u)), (int(cx - 2 * u), int(cy - 2 * u)),
                 (int(cx), int(cy + 2 * u)), (int(cx + 2 * u), int(cy - 1 * u)),
                 (int(cx + 4 * u), int(cy + 2 * u))], col, 2)
    for dx in (-3, -1, 1, 3):
        cv.line(int(cx + dx * u), int(cy - 2 * u), int(cx + dx * u), int(cy + 2 * u), col, 1)
    cv.disc(int(cx + 1 * u), int(cy - 3 * u), max(1, int(u)), (120, 130, 145))
    cv.disc(int(cx + 2 * u), int(cy - 4 * u), max(1, int(u * 0.7)), (150, 158, 170))
    cv.line(int(cx - 4 * u), int(cy + 3.5 * u), int(cx + 4 * u), int(cy + 3.5 * u), (90, 140, 190), 1)


def icon_tanker(cv, cx, cy, s, col):
    u = s / 10.0
    cv.poly([(int(cx - 4 * u), int(cy)), (int(cx + 4 * u), int(cy)),
             (int(cx + 3 * u), int(cy + 2.5 * u)), (int(cx - 3 * u), int(cy + 2.5 * u))], col)
    cv.rect(int(cx + 1 * u), int(cy - 2 * u), int(2 * u), int(2 * u), col)
    cv.poly([(int(cx - 2 * u), int(cy - 1 * u)), (int(cx - 1 * u), int(cy - 3.5 * u)),
             (int(cx), int(cy - 1 * u))], (220, 90, 30))
    cv.poly([(int(cx - 1 * u), int(cy - 1 * u)), (int(cx), int(cy - 3 * u)),
             (int(cx + 1 * u), int(cy - 1 * u))], (240, 150, 40))
    for dx in (-4, 0, 4):
        cv.line(int(cx + dx * u - u), int(cy + 3.5 * u), int(cx + dx * u + u), int(cy + 3.5 * u),
                (90, 140, 190), 1)


def icon_flags(cv, cx, cy, s, col):
    u = s / 10.0
    cols = [(37, 99, 235), (220, 38, 38), (220, 38, 38)]
    for i, fc in enumerate(cols):
        fx = int(cx + (i - 1) * 3 * u)
        cv.line(fx, int(cy - 4 * u), fx, int(cy + 3 * u), col, 1)
        cv.rect(fx, int(cy - 4 * u), int(2.4 * u), int(1.6 * u), fc)
    cv.poly([(int(cx - 4 * u), int(cy + 4 * u)), (int(cx + 4 * u), int(cy + 4 * u)),
             (int(cx), int(cy + 1.5 * u))], (90, 96, 112))


def icon_radar(cv, cx, cy, s, col):
    u = s / 10.0
    for r in (3.6, 2.4, 1.2):
        rr = max(1, int(r * u))
        for a in range(0, 360, 4):
            cv.set(int(cx + rr * math.cos(math.radians(a))),
                   int(cy + rr * math.sin(math.radians(a))), col)
    cv.line(cx, cy, int(cx + 3 * u), int(cy - 2 * u), col, 1)
    cv.disc(int(cx - 1 * u), int(cy + 1 * u), max(1, int(0.5 * u)), RED)
    cv.disc(int(cx + 2 * u), int(cy + 1 * u), max(1, int(0.5 * u)), col)


def icon_chip(cv, cx, cy, s, col):
    u = s / 10.0
    cv.rect(int(cx - 2.5 * u), int(cy - 2.5 * u), int(5 * u), int(5 * u), col)
    cv.rect(int(cx - 1.2 * u), int(cy - 1.2 * u), int(2.4 * u), int(2.4 * u), CREAM)
    for dx in (-2, 0, 2):
        cv.line(int(cx + dx * u), int(cy - 4 * u), int(cx + dx * u), int(cy - 2.5 * u), col, 1)
        cv.line(int(cx + dx * u), int(cy + 2.5 * u), int(cx + dx * u), int(cy + 4 * u), col, 1)
        cv.line(int(cx - 4 * u), int(cy + dx * u), int(cx - 2.5 * u), int(cy + dx * u), col, 1)
        cv.line(int(cx + 2.5 * u), int(cy + dx * u), int(cx + 4 * u), int(cy + dx * u), col, 1)
    cv.polyline([(int(cx + 2 * u), int(cy - 4 * u)), (int(cx + 4 * u), int(cy - 4 * u)),
                 (int(cx + 4 * u), int(cy - 2 * u))], GREEN, 1)


def icon_chartdown(cv, cx, cy, s, col):
    u = s / 10.0
    cv.line(int(cx - 4 * u), int(cy - 3.5 * u), int(cx - 4 * u), int(cy + 3.5 * u), col, 1)
    cv.line(int(cx - 4 * u), int(cy + 3.5 * u), int(cx + 4 * u), int(cy + 3.5 * u), col, 1)
    cv.polyline([(int(cx - 3.5 * u), int(cy - 3 * u)), (int(cx - 1 * u), int(cy - 1 * u)),
                 (int(cx + 1 * u), int(cy - 2 * u)), (int(cx + 3.5 * u), int(cy + 2.5 * u))],
                RED, 2)
    cv.poly([(int(cx + 3.5 * u), int(cy + 2.5 * u)), (int(cx + 2 * u), int(cy + 2.5 * u)),
             (int(cx + 3.5 * u), int(cy + 1 * u))], RED)


def icon_bankbug(cv, cx, cy, s, col):
    u = s / 10.0
    cv.poly([(int(cx - 4 * u), int(cy - 1 * u)), (int(cx), int(cy - 4 * u)),
             (int(cx + 4 * u), int(cy - 1 * u))], col)
    for dx in (-3, 0, 3):
        cv.line(int(cx + dx * u), int(cy - 1 * u), int(cx + dx * u), int(cy + 3 * u), col, 1)
    cv.line(int(cx - 4 * u), int(cy + 3 * u), int(cx + 4 * u), int(cy + 3 * u), col, 2)
    cv.disc(int(cx + 3 * u), int(cy - 3 * u), max(1, int(0.8 * u)), RED)
    cv.line(int(cx + 2 * u), int(cy - 4 * u), int(cx + 4 * u), int(cy - 4 * u), RED, 1)


def icon_rocket(cv, cx, cy, s, col):
    u = s / 10.0
    cv.poly([(int(cx), int(cy - 4.5 * u)), (int(cx + 1.5 * u), int(cy - 1 * u)),
             (int(cx + 1.5 * u), int(cy + 2 * u)), (int(cx - 1.5 * u), int(cy + 2 * u)),
             (int(cx - 1.5 * u), int(cy - 1 * u))], col)
    cv.poly([(int(cx - 1.5 * u), int(cy + 2 * u)), (int(cx - 3 * u), int(cy + 3.5 * u)),
             (int(cx - 1.5 * u), int(cy + 3 * u))], RED)
    cv.poly([(int(cx + 1.5 * u), int(cy + 2 * u)), (int(cx + 3 * u), int(cy + 3.5 * u)),
             (int(cx + 1.5 * u), int(cy + 3 * u))], RED)
    cv.disc(cx, int(cy - 1 * u), max(1, int(0.8 * u)), CREAM)
    cv.poly([(int(cx - 0.8 * u), int(cy + 2 * u)), (int(cx + 0.8 * u), int(cy + 2 * u)),
             (int(cx), int(cy + 4.5 * u))], (240, 150, 40))


def icon_virus(cv, cx, cy, s, col):
    u = s / 10.0
    for a in range(0, 360, 45):
        x2 = int(cx + 3.6 * u * math.cos(math.radians(a)))
        y2 = int(cy + 3.6 * u * math.sin(math.radians(a)))
        cv.line(cx, cy, x2, y2, col, 1)
        cv.disc(x2, y2, max(1, int(0.5 * u)), col)
    cv.disc(cx, cy, max(1, int(1.8 * u)), col)
    cv.disc(int(cx - 0.7 * u), int(cy - 0.7 * u), max(1, int(0.5 * u)), CREAM)


def icon_planedoor(cv, cx, cy, s, col):
    u = s / 10.0
    cv.rect(int(cx - 4 * u), int(cy - 3 * u), int(3 * u), int(6 * u), col)
    cv.rect(int(cx - 3.2 * u), int(cy - 2.2 * u), int(1.4 * u), int(4.4 * u), CREAM)
    cv.poly([(int(cx + 1 * u), int(cy - 1 * u)), (int(cx + 4 * u), int(cy - 1 * u)),
             (int(cx + 2.5 * u), int(cy + 1 * u))], col)
    cv.line(int(cx + 1 * u), int(cy - 2.5 * u), int(cx + 4 * u), int(cy - 2.5 * u), col, 1)


def icon_jet(cv, cx, cy, s, col):
    u = s / 10.0
    cv.poly([(int(cx - 4 * u), int(cy)), (int(cx + 4 * u), int(cy - 1 * u)),
             (int(cx + 2 * u), int(cy + 1 * u)), (int(cx - 2 * u), int(cy + 1.5 * u))], col)
    cv.poly([(int(cx), int(cy)), (int(cx + 1 * u), int(cy + 3 * u)),
             (int(cx - 1 * u), int(cy + 2 * u))], col)
    cv.line(int(cx - 4 * u), int(cy), int(cx - 5 * u), int(cy - 1 * u), (200, 200, 200), 1)


def icon_parliament(cv, cx, cy, s, col):
    u = s / 10.0
    cv.poly([(int(cx - 2 * u), int(cy - 1 * u)), (int(cx - 2 * u), int(cy - 2.5 * u)),
             (int(cx), int(cy - 4 * u)), (int(cx + 2 * u), int(cy - 2.5 * u)),
             (int(cx + 2 * u), int(cy - 1 * u))], col)
    for dx in (-3, -1, 1, 3):
        cv.line(int(cx + dx * u), int(cy - 1 * u), int(cx + dx * u), int(cy + 3 * u), col, 1)
    cv.line(int(cx - 4 * u), int(cy + 3 * u), int(cx + 4 * u), int(cy + 3 * u), col, 2)


def icon_tv(cv, cx, cy, s, col):
    u = s / 10.0
    cv.rect(int(cx - 6 * u), int(cy - 3 * u), int(12 * u), int(5.5 * u), col)
    cv.rect(int(cx - 5.4 * u), int(cy - 2.4 * u), int(10.8 * u), int(4.3 * u), (20, 24, 40))
    draw_centered(cv, cx, int(cy - 1.6 * u), "ALSOB", "OFF AIR", (255, 255, 255))
    cv.line(int(cx - 1 * u), int(cy + 2.5 * u), int(cx + 1 * u), int(cy + 2.5 * u), col, 1)
    cv.line(int(cx - 2 * u), int(cy + 3.5 * u), int(cx + 2 * u), int(cy + 3.5 * u), col, 1)


def icon_cross(cv, cx, cy, s, col):
    u = s / 10.0
    cv.rect(int(cx - 0.8 * u), int(cy - 4 * u), int(1.6 * u), int(8 * u), col)
    cv.rect(int(cx - 2.6 * u), int(cy - 2.4 * u), int(5.2 * u), int(1.6 * u), col)
    cv.disc(int(cx + 3 * u), int(cy - 3 * u), max(1, int(0.9 * u)), (200, 200, 210))


ICONS = {"bridge": icon_bridge, "tanker": icon_tanker, "flags": icon_flags,
         "radar": icon_radar, "chip": icon_chip, "chartdown": icon_chartdown,
         "bankbug": icon_bankbug, "rocket": icon_rocket, "virus": icon_virus,
         "planedoor": icon_planedoor, "jet": icon_jet, "parliament": icon_parliament,
         "tv": icon_tv, "cross": icon_cross}


# ---- world map (dot-matrix from coarse lon/lat polygons) ----
LAND_POLYS = [
    # North America
    [(-168, 66), (-140, 70), (-125, 71), (-110, 68), (-95, 69), (-85, 66),
     (-76, 62), (-65, 60), (-55, 52), (-60, 47), (-65, 44), (-70, 42),
     (-75, 35), (-80, 32), (-81, 26), (-84, 30), (-90, 21), (-97, 26),
     (-105, 22), (-110, 24), (-117, 32), (-125, 40), (-124, 48), (-130, 55),
     (-145, 60), (-158, 58), (-168, 66)],
    # Central America
    [(-105, 20), (-97, 16), (-92, 15), (-86, 12), (-83, 9), (-79, 9),
     (-83, 13), (-90, 15), (-97, 18), (-104, 22)],
    # Greenland
    [(-58, 64), (-45, 60), (-30, 68), (-22, 70), (-30, 76), (-45, 80),
     (-58, 76), (-62, 70)],
    # South America
    [(-79, 9), (-77, 4), (-80, -3), (-81, -6), (-77, -12), (-72, -18),
     (-70, -23), (-70, -30), (-72, -37), (-73, -44), (-70, -52), (-66, -55),
     (-68, -50), (-65, -45), (-62, -40), (-58, -34), (-52, -32), (-48, -28),
     (-41, -23), (-39, -17), (-35, -9), (-35, -6), (-40, -3), (-44, -2),
     (-50, 0), (-53, 4), (-60, 8), (-70, 11), (-75, 10)],
    # UK
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (0, 57), (-1, 52)],
    # Europe
    [(-10, 36), (-9, 43), (-2, 48), (-5, 50), (0, 51), (3, 53), (8, 57),
     (10, 59), (18, 56), (21, 55), (24, 58), (28, 60), (30, 62), (25, 65),
     (30, 70), (40, 68), (44, 66), (40, 60), (35, 55), (30, 50), (28, 45),
     (23, 40), (19, 42), (12, 44), (8, 44), (3, 43), (-1, 38), (-6, 36)],
    # Africa
    [(-6, 35), (-10, 31), (-15, 27), (-17, 21), (-17, 15), (-15, 11),
     (-12, 8), (-8, 5), (-4, 5), (2, 6), (6, 4), (9, 4), (9, -1), (12, -5),
     (13, -10), (12, -17), (14, -22), (16, -28), (19, -34), (26, -34),
     (32, -29), (35, -24), (40, -16), (40, -10), (42, -4), (46, -1), (51, 2),
     (51, 10), (48, 11), (44, 12), (40, 15), (38, 18), (37, 22), (35, 28),
     (32, 31), (25, 32), (19, 33), (11, 34), (10, 37), (5, 37)],
    # Middle East
    [(35, 42), (44, 38), (48, 30), (50, 26), (56, 26), (58, 22), (54, 17),
     (48, 16), (44, 15), (42, 18), (39, 21), (35, 29), (34, 36)],
    # India
    [(68, 24), (72, 20), (76, 18), (78, 8), (80, 10), (84, 14), (88, 22),
     (88, 26), (84, 26), (80, 24), (76, 24), (72, 26)],
    # SE Asia
    [(94, 22), (98, 16), (100, 14), (101, 8), (104, 2), (104, 8), (108, 11),
     (109, 16), (106, 20), (102, 22), (98, 24)],
    # China
    [(98, 30), (105, 28), (110, 25), (115, 24), (120, 28), (122, 32),
     (120, 38), (115, 40), (110, 40), (105, 38), (100, 35), (98, 32)],
    # North Asia / Siberia
    [(60, 55), (70, 60), (80, 65), (90, 70), (100, 72), (110, 72), (120, 70),
     (130, 68), (140, 68), (150, 70), (160, 68), (170, 66), (178, 65),
     (170, 60), (160, 58), (150, 55), (140, 52), (135, 45), (130, 42),
     (125, 40), (120, 38), (110, 42), (100, 45), (90, 48), (80, 50), (70, 52)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (138, 35), (140, 38), (141, 42),
     (142, 44), (140, 40), (137, 36), (133, 33)],
    # Indonesia
    [(95, 5), (100, 0), (105, -5), (110, -7), (115, -8), (120, -10),
     (125, -9), (130, -4), (135, -3), (140, -8), (138, -9), (130, -10),
     (120, -11), (110, -8), (100, -4), (95, 2)],
    # Australia
    [(113, -22), (114, -30), (115, -35), (120, -34), (124, -33), (129, -32),
     (132, -32), (135, -35), (138, -35), (140, -38), (145, -38), (150, -37),
     (153, -32), (153, -27), (150, -22), (146, -19), (142, -15), (142, -11),
     (137, -12), (135, -15), (132, -12), (130, -13), (126, -14), (122, -17),
     (118, -20)],
    # New Zealand
    [(167, -35), (170, -40), (172, -42), (174, -41), (170, -37)],
]


def _in_poly(lon, lat, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > lat) != (y1 > lat):
            xin = x0 + (lat - y0) * (x1 - x0) / (y1 - y0)
            if lon < xin:
                inside = not inside
    return inside


def _on_land(lon, lat):
    return any(_in_poly(lon, lat, p) for p in LAND_POLYS)


# (story, lon, lat, chip dx, chip dy, pin colour)
PINS = [
    (1, 36.5, 45.3, 10, -26, BLUE),
    (2, 50.5, 26.2, 14, -24, RED),
    (3, 56.5, 26.5, 16, 10, RED),
    (4, 121.0, 14.6, 10, -22, TEAL),
    (5, -122.0, 37.4, -28, -20, GREEN),
    (6, -74.0, 40.7, 8, -24, GREEN),
    (7, -74.0, 40.7, -32, 20, GREEN),
    (8, -80.5, 28.4, 16, -6, GREEN),
    (9, 25.0, -2.0, 10, -22, ORANGE),
    (10, -98.0, 39.0, -26, -6, GREEN),
    (11, 4.4, 50.8, -30, -18, BLUE),
    (12, 139.7, 35.7, 10, -22, TEAL),
    (13, 106.9, 47.9, 12, -22, TEAL),
    (14, 32.9, 39.9, -34, 8, BLUE),
    (15, -77.0, -12.0, 12, -20, PURPLE),
]

MAP_X, MAP_Y, MAP_W, MAP_H = 6, 740, 364, 158


def map_xy(lon, lat):
    x = MAP_X + (lon + 170) * (MAP_W / 360.0)
    y = MAP_Y + (80 - lat) * (MAP_H / 138.0)
    return int(round(x)), int(round(y))


def draw_map(cv):
    lat = 78.0
    while lat > -56:
        lon = -168.0
        while lon < 188:
            if _on_land(lon, lat):
                x, y = map_xy(lon, lat)
                cv.rect(x - 1, y - 1, 3, 3, LAND)
            lon += 4.0
        lat -= 3.5
    for num, lon, lat, dx, dy, col in PINS:
        px, py = map_xy(lon, lat)
        cx, cy = px + dx, py + dy
        cv.line(cx + 10, cy + 7, px, py, (90, 96, 112), 1)
        cv.disc(px, py, 3, col)
        cv.disc(px, py, 1, (255, 255, 255))
        cv.rect(cx, cy, 20, 15, col)
        draw_centered(cv, cx + 10, cy + 2, "CHIP", str(num), (255, 255, 255))
    draw_centered(cv, map_xy(-140, -25)[0], map_xy(-140, -25)[1], "LEGEND", "PACIFIC", OCEAN_LBL)
    draw_centered(cv, map_xy(-20, -35)[0], map_xy(-20, -35)[1], "LEGEND", "ATLANTIC", OCEAN_LBL)
    draw_centered(cv, map_xy(80, -25)[0], map_xy(80, -25)[1], "LEGEND", "INDIAN", OCEAN_LBL)


def draw_legend(cv):
    rows = [[(GREEN, "N. AMERICA"), (GREEN, "S. AMERICA"), (BLUE, "EUROPE")],
            [(ORANGE, "AFRICA"), (TEAL, "ASIA"), (TEAL, "OCEANIA"), (GREY, "GLOBAL")]]
    y = 904
    for row in rows:
        x = 6
        for col, label in row:
            cv.rect(x, y + 1, 7, 7, col)
            x += 10
            x = draw_text(cv, x, y, "LEGEND", label, INK)
            x += 10
        y += 14


# ---- layout ----
def draw_masthead(cv):
    cv.rect(0, 0, W, 136, NAVY)
    draw_tracked(cv, 20, 14, "NAMEPLATE", "LATENT ATLAS", GOLD, 5)
    draw_text(cv, W - 20 - text_w("SMALLB", "ONE DAY, ONE PLANET"), 20,
              "SMALLB", "ONE DAY, ONE PLANET", GOLD)
    draw_centered(cv, W // 2, 50, "MASTHEAD", "TUESDAY 17 NOVEMBER 2026", (255, 255, 255))
    bw = text_w("BADGE", "34 STORIES \u00b7 6 CONTINENTS \u00b7 ONE DAY") + 28
    bx = (W - bw) // 2
    cv.rect(bx, 102, bw, 26, GOLD)
    draw_centered(cv, W // 2, 108, "BADGE", "34 STORIES \u00b7 6 CONTINENTS \u00b7 ONE DAY", NAVY)


def draw_leads(cv):
    for i, lead in enumerate(LEADS):
        x = 6 + i * 339
        y, w, h = 136, 333, 176
        cv.rect(x, y, w, h, CARD)
        for xx in range(x, x + w):
            cv.set(xx, y, FRAME)
            cv.set(xx, y + h - 1, FRAME)
        for yy in range(y, y + h):
            cv.set(x, yy, FRAME)
            cv.set(x + w - 1, yy, FRAME)
        cv.rect(x + 1, y + 1, w - 2, 52, lead["band"])
        ICONS[lead["icon"]](cv, x + w // 2, y + 27, 44, lead["color"])
        draw_text(cv, x + 4, y + 60, "KICKER", lead["kicker"], lead["color"])
        yy = y + 76
        for ln in lead["head"]:
            draw_text(cv, x + 4, yy, "LEAD", ln, INK)
            yy += 25
        yy = y + 152
        for ln in lead["deck"]:
            draw_text(cv, x + 4, yy, "DECK", ln, MUTED)
            yy += 12


def draw_cards(cv):
    for i, card in enumerate(CARDS):
        col, row = i % 3, i // 3
        x = 6 + col * 339
        y = 314 + row * 107
        w, h = 333, 104
        cv.rect(x, y, w, h, CARD)
        for xx in range(x, x + w):
            cv.set(xx, y, FRAME)
            cv.set(xx, y + h - 1, FRAME)
        for yy in range(y, y + h):
            cv.set(x, yy, FRAME)
            cv.set(x + w - 1, yy, FRAME)
        # number chip in the icon rail
        cv.disc(x + 28, y + 15, 10, card["color"])
        draw_centered(cv, x + 28, y + 8, "CHIP", str(card["num"]), (255, 255, 255))
        ICONS[card["icon"]](cv, x + 28, y + 62, 34, card["color"])
        tx = x + 56
        draw_text(cv, tx, y + 6, "KICKER", card["kicker"], card["color"])
        yy = y + 20
        for ln in card["head"]:
            draw_text(cv, tx, yy, "HEAD", ln, INK)
            yy += 20
        yy = y + 80
        for ln in card["deck"]:
            draw_text(cv, tx, yy, "DECKSM", ln, MUTED)
            yy += 11


def draw_bottom(cv):
    draw_map(cv)
    draw_legend(cv)
    # ALSO list
    draw_text(cv, 388, 744, "STRIP", "ALSO ON 16-33", NAVY)
    cv.rect(388, 764, 628, 2, GOLD)
    for i, item in enumerate(ALSO):
        col = i % 2
        row = i // 2
        x = 388 + col * 318
        y = 772 + row * 18
        num, _, rest = item.partition(". ")
        draw_text(cv, x, y, "ALSOB", num + ".", RED)
        draw_text(cv, x + text_w("ALSOB", num + ".") + 4, y, "ALSO", rest, INK)


def draw_strip_footer(cv):
    cv.rect(0, 930, W, 48, GOLD)
    draw_centered(cv, W // 2, 948, "STRIP", STRIP, NAVY)
    draw_centered(cv, W // 2, 984, "FOOTER", FOOT1, INK)
    draw_centered(cv, W // 2, 1002, "FOOTERSM", FOOT2, MUTED)


# ---- PNG writer (deterministic) ----
def chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(cv, path):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    cv = Canvas(W, H, CREAM)
    draw_masthead(cv)
    draw_leads(cv)
    draw_cards(cv)
    draw_bottom(cv)
    draw_strip_footer(cv)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")
    path = os.path.join(outdir, "entry.png")
    n = write_png(cv, path)
    print("wrote", path, n, "bytes")


if __name__ == "__main__":
    main()
