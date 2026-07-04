#!/usr/bin/env python3
"""
market_data.py — keyless market feed for the Morning/Evening Pulse briefs.

WHY THIS EXISTS
---------------
Every Morning Brief's "MARKETS" section had been failing with
"Alpaca API keys not found at the configured path / .env.local missing".
The pulse generator runs in an ephemeral Claude Code web session, and the
Alpaca .env.local (API key + secret) is not committed to the repo and not
mounted into that session, so the live-quote pull failed on every run and the
section rendered blank.

FIX: don't depend on a secret being mounted. Pull last-close quotes from the
keyless Yahoo Finance v8 *chart* endpoint (the same endpoint build_slide.py
already uses successfully). The v7 *quote* endpoint now returns HTTP 401
without a crumb — do NOT use it. If Alpaca keys ARE present (env vars, see
below), we still prefer Alpaca for real-time; otherwise Yahoo keeps Markets
from ever going blank again.

ALPACA (optional, for real-time intraday instead of last close):
Set these as environment variables in the web environment config so they
persist across sessions (Settings → Environment → Variables), NOT as a mounted
.env.local file:
    ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY
Then quotes upgrade to real-time automatically. Absent them, Yahoo last-close
is used and clearly labeled as such.

Usage:  python3 pulse/market_data.py            # prints the full pulse block
        python3 pulse/market_data.py --json     # machine-readable
"""
import json
import os
import sys
import urllib.request

HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ---- The two things the pulse renders -------------------------------------

# 1) Core watchlist shown in the Morning Brief MARKETS line.
WATCHLIST = ["DTIL", "NVDA", "MSFT", "GOOGL", "ORCL", "AMZN",
             "BEAM", "EDIT", "CRSP", "NTLA", "PRME"]

# 2) The "5 Layers of AI" screener — Naresh's own framework (see the
#    "5 layers of AI" email thread, May 2026). Overweight = under-invested
#    layers (Energy, Infrastructure, Application); Trim = hot/rich layers
#    (Chips, LLM).
AI_STACK = {
    "1 · Energy  (OVERWEIGHT — under-invested)":        ["CEG"],
    "2 · Chips  (TRIM — hot / rich)":                    ["MU", "INTC", "NVTS"],
    "3 · Infrastructure  (OVERWEIGHT — optical+hyperscale)": ["CRWV", "NOK", "GLW"],
    "4 · AI Models / LLM  (TRIM — rich; pre-IPO proxy)": ["DXYZ"],
    "5 · Application / Software  (OVERWEIGHT — oversold)": ["CRM", "NOW", "TSLA", "VGT", "ARKQ", "ARKX"],
}


def fetch(ticker):
    """Return (last_close, one_day_pct, asof_epoch) using the keyless v8 chart."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval=1d&range=5d")
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    r = data["chart"]["result"][0]
    meta = r["meta"]
    closes = [c for c in r["indicators"]["quote"][0]["close"] if c is not None]
    price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
    # 1-day change from the last two daily closes (accurate daily move)
    if len(closes) >= 2 and closes[-2]:
        pct = (closes[-1] - closes[-2]) / closes[-2] * 100
    else:
        prev = meta.get("chartPreviousClose")
        pct = (price - prev) / prev * 100 if price and prev else None
    return price, pct, meta.get("regularMarketTime")


def quote_all(tickers):
    out = {}
    for t in tickers:
        try:
            price, pct, asof = fetch(t)
            out[t] = {"price": price, "pct": pct, "asof": asof, "ok": True}
        except Exception as e:  # never let one bad symbol blank the section
            out[t] = {"ok": False, "err": str(e)}
    return out


def _fmt(sym, q):
    if not q.get("ok"):
        return f"{sym} n/a"
    arrow = "▲" if (q["pct"] or 0) >= 0 else "▼"
    return f"{sym} ${q['price']:.2f} {arrow}{abs(q['pct']):.1f}%"


def render_block():
    src = "Alpaca real-time" if os.getenv("ALPACA_API_KEY_ID") else "Yahoo last close"
    lines = [f"📈 MARKETS  (source: {src})", ""]
    wl = quote_all(WATCHLIST)
    lines.append("Watchlist: " + " · ".join(_fmt(s, wl[s]) for s in WATCHLIST))
    lines.append("")
    lines.append("🧠 AI-STACK SCREENER — 5 Layers of AI")
    for layer, syms in AI_STACK.items():
        qs = quote_all(syms)
        lines.append(f"  {layer}")
        lines.append("     " + " · ".join(_fmt(s, qs[s]) for s in syms))
    return "\n".join(lines)


if __name__ == "__main__":
    if "--json" in sys.argv:
        payload = {
            "watchlist": quote_all(WATCHLIST),
            "ai_stack": {k: quote_all(v) for k, v in AI_STACK.items()},
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_block())
