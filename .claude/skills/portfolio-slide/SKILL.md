---
name: portfolio-slide
description: Build the biotech portfolio performance PowerPoint deck (DTIL, PRME, BEAM, EDIT, CRSP, NTLA). Use whenever the user asks for their portfolio slide, portfolio deck, biotech performance update, or how their portfolio/tickers did over the last month or another window.
---

# Portfolio Performance Slide

Builds a single widescreen dark-theme slide with a normalized-return line
chart, a return scoreboard, and per-ticker scorecards, using fresh prices
from Yahoo Finance.

## How to run

From the repo root:

```bash
pip install -r cowork_bridge/requirements.txt   # first time only
python build_slide.py                           # default portfolio, 30 days
```

For a custom ticker list, window, or title, call the library directly:

```bash
python -c "
from cowork_bridge.portfolio import build_portfolio_slide
path, data = build_portfolio_slide(tickers=['DTIL','PRME','BEAM'], days=90)
print(path)
"
```

The deck is saved in the repo root (e.g. `Biotech_Portfolio_1Month.pptx`).
Send the resulting file to the user.

## Notes

- The first ticker in the list is treated as the primary focus (drawn
  thicker on the chart); DTIL is the default focus.
- Scorecards render for at most six tickers.
- If a ticker fails to fetch, the slide still builds and that ticker shows
  N/A — report which tickers errored (`data['errors']`).
- If only numbers are wanted (no deck), use
  `cowork_bridge.portfolio.fetch_performance(tickers, days)`.
