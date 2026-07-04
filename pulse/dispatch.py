#!/usr/bin/env python3
"""
dispatch.py — the streamlined Pulse dispatcher.

GOAL: exactly TWO emails per day — one Morning Pulse, one Evening Pulse.
Everything that used to arrive as a separate email is now a *section* inside
one of those two, composed by a single job.

BEFORE (fragmented — up to 5 emails/day)        AFTER (streamlined — 2/day)
────────────────────────────────────────        ──────────────────────────
☀️ Morning Brief            ┐                     ☀️ MORNING PULSE  (1 job, 7:00 AM ET)
🧭 TMC Daily (sports+trips) ├─ fold in ──────►      = brief + sports + trips + markets
✈️ TMC Trip Scout (weekly)  ┘                          + AI-stack + news + weather + health
🌙 Evening Brief            ┐                     🌙 EVENING PULSE  (1 job, 8:30 PM ET)
🌙 TMC Cowork nightly       ┘─ fold in ──────►      = tomorrow + actions + nightly systems + health

Key properties:
  • ONE dispatch per slot fans OUT to data collectors, fans IN to ONE email.
  • Header date is stamped in ET (pulse_dates) — never UTC (fixes the off-by-one).
  • Markets/AI-stack section is real & keyless (market_data) — never blanks.
  • The weekly Trip Scout rotates into Monday's Morning Pulse (no separate email).

Run:
  python3 pulse/dispatch.py --list          # show the 2 jobs + schedule
  python3 pulse/dispatch.py morning         # compose the morning email
  python3 pulse/dispatch.py evening         # compose the evening email
"""
import sys

from pulse_dates import header_date, now_et
import market_data

# ── The two jobs. This is the whole schedule. ──────────────────────────────
JOBS = {
    "morning": {
        "emoji": "☀️",
        "title": "Morning Pulse",
        "cron_et": "0 7 * * *",          # 7:00 AM America/New_York, daily
        "subject": lambda: f"☀️ Morning Pulse — {header_date()}",
        # ordered sections; folds in the old Morning Brief + TMC Daily + Trip Scout
        "sections": [
            "decisions",       # 🔴 needs-a-decision (top)
            "wealth",          # 💰 markets + AI-stack screener + news   [LIVE via market_data]
            "biotech",         # 🧬 DTIL / CFO track
            "family_today",    # 👨‍👩‍👦 today's calendar
            "sports_14d",      # 🏊 kids sports next 14 days   (was: TMC Daily)
            "trips",           # 🧳 trip checkpoints + weekly scout   (was: Trip Scout, Mondays)
            "health",          # 🧠 protocol
            "admin",           # 📋 bills + weather
        ],
    },
    "evening": {
        "emoji": "🌙",
        "title": "Evening Pulse",
        "cron_et": "30 20 * * *",        # 8:30 PM America/New_York, daily
        "subject": lambda: f"🌙 Evening Pulse — {header_date()}",
        # folds in the old Evening Brief + TMC Cowork nightly
        "sections": [
            "decisions_top3",  # 🔴 top-3 to decide this week
            "tomorrow",        # 📅 tomorrow's plan
            "wealth_note",     # 💰 overnight market note
            "family_trips",    # 👨‍👩‍👦 family + trips status
            "actions",         # 📋 bills / decisions
            "health",          # 🧠 protocol
            "systems",         # 🌙 nightly systems + inbox   (was: TMC Cowork nightly)
        ],
    },
}

# Sections retired as standalone emails (now folded into the two jobs above).
RETIRED_EMAILS = [
    "🧭 TMC Daily (sports + trip prep)  → Morning Pulse §sports_14d + §trips",
    "✈️ TMC Trip Scout (weekly)         → Morning Pulse §trips (Monday rotation)",
    "🌙 TMC Cowork nightly              → Evening Pulse §systems",
]

# Where each live section gets its data (documented so the Cowork run fills them).
SOURCES = {
    "wealth": "market_data.render_block()  [LIVE, keyless]",
    "sports_14d": "Google Family calendar (next 14 days)",
    "trips": "TMC dashboard CONFIRMED_TRIPS + checkpoint clock (T-30/14/7/3/1)",
    "biotech": "news search (DTIL + gene-editing peers) + CFO course queue",
    "family_today": "Google primary + Family calendar (today)",
    "tomorrow": "Google calendars (tomorrow)",
    "admin": "Gmail bill/statement scan + weather API (Cary, NC)",
    "actions": "Gmail bill/decision scan",
    "health": "peptide protocol schedule (Sermorelin / tirzepatide / labs)",
    "systems": "Vercel deploy + [TMC-INBOX] captures + bookable confirmations",
}


def _live_wealth():
    """The only section with live data wired in here; the rest are Cowork-filled."""
    try:
        return market_data.render_block()
    except Exception as e:
        return f"📈 MARKETS — feed error ({e}); Cowork run will retry."


def compose(job_key: str) -> str:
    job = JOBS[job_key]
    out = [job["subject"](), ""]
    for name in job["sections"]:
        if name == "wealth":
            out.append(_live_wealth())
        else:
            src = SOURCES.get(name, "Cowork runtime")
            out.append(f"[§ {name}]  ← {src}")
        out.append("")
    out.append(f"— Tanna Mission Control · {job['title']} "
               f"(one email per slot; draft only, nothing sent/booked/charged)")
    return "\n".join(out)


def show_schedule():
    print("STREAMLINED PULSE — 2 jobs total\n")
    for k, j in JOBS.items():
        print(f"{j['emoji']} {j['title']:14s}  cron(ET) {j['cron_et']:12s}  "
              f"{len(j['sections'])} sections")
    print("\nRetired as standalone emails (now folded in):")
    for r in RETIRED_EMAILS:
        print("  •", r)
    print(f"\nStamped in ET — now: {now_et():%A, %B %d %Y  %H:%M %Z}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--list"
    if arg in ("--list", "-l"):
        show_schedule()
    elif arg in JOBS:
        print(compose(arg))
    else:
        print(f"usage: dispatch.py [--list | morning | evening]", file=sys.stderr)
        sys.exit(1)
