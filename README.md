# news-image-20261117 — "Kind Forge" (iteration 3)

[![make.fun · news-image-20261117](https://make.fun/badge/news-image-20261117.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![rank](https://make.fun/badge/news-image-20261117/tiVan0/news-image-20261117/rank.svg)](https://make.fun/bounty/news-image-20261117/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![reward](https://make.fun/badge/news-image-20261117/tiVan0/news-image-20261117/reward.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)

Entry for the [make.fun](https://make.fun/c/news-image-20261117/) bounty
**"Sum up 17 November's world news in one image"** ($250).

One newspaper front page for one day on one planet: a navy masthead with
a giant serif date, three fully illustrated leads, twelve numbered cards
in a 4×3 grid — every card with its own drawn scene — a soft cream-on-blue
world map with fifteen numbered pins, a 27-item ALSO list, a four-figure
strip, and a gold strip closing with NASA's Voyager 1 "shine a light" night.

## The image

- **Date, unmissable:** `TUESDAY 17 NOVEMBER 2026` in 56pt serif.
- **43 stories · 6 continents · one day** — 3 leads + 12 cards + 27 ALSO
  items + the Voyager strip, numbered 1–43 throughout the page.
- Every story is verified from reporting of 17 November 2026 (Reuters,
  AP, AFP, BBC, Al Jazeera, WHO, UN News, NASA, TechCrunch). Disputed
  claims are attributed in the headline itself ("Iran says…",
  "Russia says…", "US says…"); Voyager "nears" one light-day — it does
  not reach it until 18 Nov; the cyclone landfall is a forecast for
  Friday, not a Tuesday event.
- **No AI-generated text:** the picture is drawn from scratch by
  `main.py` — flat vector shapes plus bitmap DejaVu glyphs — so there is
  no garbled text, no smear, no artefact. Date, lead headlines and all
  twelve card headlines stay readable at 300px wide.

## How it runs

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png
```

Pure Python 3 standard library only (no network, no PIL at runtime):
`main.py` reads the bitmap glyph tables in `font_tables.json`, draws the
1024×1024 board, and writes a deterministic PNG (two runs, identical
bytes; 51,480 bytes, well under the 1 MiB limit).

## Files

| File | What it is |
| --- | --- |
| `main.py` | The entrypoint: draws the image from scratch |
| `font_tables.json` | Bitmap DejaVu glyph tables (data, generated at build time) |
| `LICENSE` | MIT |
| `.makefun/owner.json` | Claim file naming the payout wallet |

## License

MIT — see [LICENSE](LICENSE).
