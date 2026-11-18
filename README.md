# news-image-20261117 — "Latent Atlas" (iterasi 1)

[![make.fun · news-image-20261117](https://make.fun/badge/news-image-20261117.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![rank](https://make.fun/badge/news-image-20261117/tiVan0/news-image-20261117/rank.svg)](https://make.fun/bounty/news-image-20261117/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![reward](https://make.fun/badge/news-image-20261117/tiVan0/news-image-20261117/reward.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)

Entry for the [make.fun](https://make.fun/c/news-image-20261117/) bounty
**"Sum up 17 November's world news in one image"** ($250).

A newspaper front page for one day on one planet: a dark-navy masthead
with a giant serif date, three illustrated leads, twelve numbered cards
with region kickers, a dot-matrix world map with fifteen numbered pins,
an ALSO list, and a gold strip closing with NASA's Voyager 1
"shine a light" night.

## The image

- **Date, unmissable:** `TUESDAY 17 NOVEMBER 2026` in 56pt serif.
- **34 stories · 6 continents · one day** — 3 leads + 12 cards + 18 ALSO
  items + the Voyager strip, numbered 1–34 throughout the page.
- All verified from reporting of 17 November 2026 (Reuters, AP, AFP,
  BBC, Al Jazeera, WHO, UN News, NASA, TechCrunch). Disputed claims are
  attributed in the headline itself ("Iran says…", "US says…");
  Voyager "nears" one light-day — it does not reach it until 18 Nov.
- **No AI-generated text:** the picture is drawn from scratch by
  `main.py` — flat vector shapes plus bitmap DejaVu glyphs — so there
  is no garbled text, no smear, no artefact. Every headline stays
  readable at 300px wide.

## How it runs

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png
```

Pure Python 3 standard library only (no network, no PIL at runtime):
`main.py` reads the bitmap glyph tables in `font_tables.json`, draws
the 1024×1024 board, and writes a deterministic PNG (two runs,
identical bytes; 50,544 bytes, well under the 1 MiB limit).

## Files

| File | What it is |
| --- | --- |
| `main.py` | The entrypoint: draws the image from scratch |
| `font_tables.json` | Bitmap DejaVu glyph tables (data, generated at build time) |
| `LICENSE` | MIT |
| `.makefun/owner.json` | Claim file naming the payout wallet |

## License

MIT — see [LICENSE](LICENSE).
