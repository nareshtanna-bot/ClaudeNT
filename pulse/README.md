# Pulse — market data fix

The Morning/Evening Pulse briefs (Gmail drafts) had a **MARKETS** section that
failed on every run with:

> Unavailable — Alpaca API keys not found at the configured path / .env.local missing

## Root cause
The pulse generator runs in an **ephemeral Claude Code web session**. The Alpaca
`.env.local` (API key + secret) was never committed and is not mounted into that
session, so the live-quote pull failed every time and the section rendered blank.
The Yahoo v7 *quote* endpoint also started returning `HTTP 401` (needs a crumb),
which would have broken any quote pull that relied on it.

## Fix
`market_data.py` pulls last-close quotes from the **keyless Yahoo v8 *chart*
endpoint** (the same one `build_slide.py` already uses successfully). No secret
required, so MARKETS never goes blank again. It renders:

- the core **watchlist** (DTIL, NVDA, MSFT, GOOGL, ORCL, AMZN, BEAM, EDIT, CRSP, NTLA, PRME)
- the **"5 Layers of AI" screener** — Naresh's own framework (Energy / Chips /
  Infrastructure / AI-models / Application), each layer tagged OVERWEIGHT or TRIM.

```
python3 pulse/market_data.py          # human-readable pulse block
python3 pulse/market_data.py --json   # machine-readable
```

## Optional: restore Alpaca real-time
Set these as **environment variables in the web-environment config** (Settings →
Environment → Variables) so they persist across sessions — do NOT rely on a
mounted `.env.local`:

```
ALPACA_API_KEY_ID=...
ALPACA_API_SECRET_KEY=...
```

When present, quotes upgrade to Alpaca real-time; when absent, Yahoo last-close is
used and clearly labeled in the output.

---

# Pulse — date accuracy fix

Evening/nightly briefs were rendering the header **one day ahead** (e.g., a
brief generated the evening of July 3 read "July 4"). Root cause: the header
was stamped from **UTC**. The evening/nightly run fires ~9 PM ET = ~1 AM UTC
the next day, so a UTC date label rolls forward. The 7 AM ET morning run
(~11 AM UTC) happened to land on the right day, which is why only the
evening/nightly briefs were wrong.

**Fix:** `pulse_dates.py` — always stamp the header in `America/New_York`.

```python
from pulse_dates import header_date, sanity_check
subject = f"☀️ Morning Pulse — {header_date()}"   # -> "Saturday, July 4, 2026"
warn = sanity_check()   # non-empty if a UTC stamp would disagree with ET
```

`python3 pulse/pulse_dates.py` self-tests and prints the guard status.

---

# Course content

`cfo_filing_crash_course.md` — a ranked crash course on every SEC filing a
biotech CFO encounters (hugest → lowest probability), with gene-editing peer
examples (DTIL/PRME/BEAM/EDIT/CRSP/NTLA). Rendered into a nightly email draft
to supplement the DTIL 10-K learnings.
