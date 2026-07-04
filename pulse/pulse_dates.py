#!/usr/bin/env python3
"""
pulse_dates.py — canonical date/time for the Morning/Evening Pulse.

WHY THIS EXISTS
---------------
The pulse header date was rendering one day AHEAD on evening/nightly runs.
Root cause: the generator stamped the header from UTC. The evening/nightly
run fires ~9:00 PM ET, which is ~01:00 UTC the *next* calendar day, so a
UTC date label reads tomorrow. The 7 AM ET morning run (~11:00 UTC) happens
to land on the right day, which is why only the evening/nightly briefs were
wrong ("yesterday's email said the 4th when it was the 3rd").

RULE: every pulse timestamp is Naresh's local time — America/New_York.
Never stamp the header from UTC or the container's naive local clock.

    from pulse_dates import header_date, now_et
    subject = f"☀️ Morning Pulse — {header_date()}"
    # -> "Saturday, July 4, 2026"
"""
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def now_et() -> datetime:
    """Current time in America/New_York (the only clock the pulse should use)."""
    return datetime.now(ET)


def header_date(dt: datetime | None = None) -> str:
    """Human header date in ET, e.g. 'Saturday, July 4, 2026'."""
    dt = dt or now_et()
    # %-d = no leading zero (Linux). Fallback to lstrip for portability.
    try:
        return dt.strftime("%A, %B %-d, %Y")
    except ValueError:
        return dt.strftime("%A, %B ") + str(dt.day) + dt.strftime(", %Y")


def iso_et(dt: datetime | None = None) -> str:
    """ISO stamp with ET offset, e.g. '2026-07-04T21:00:00-04:00'."""
    return (dt or now_et()).replace(microsecond=0).isoformat()


def sanity_check(dt: datetime | None = None) -> str:
    """Return a warning string if a UTC stamp would disagree with ET, else ''."""
    dt = dt or now_et()
    utc_date = dt.astimezone(ZoneInfo("UTC")).date()
    if utc_date != dt.date():
        return (f"⚠️ DATE GUARD: UTC ({utc_date}) is ahead of ET "
                f"({dt.date()}). Use ET ({header_date(dt)}) for the header.")
    return ""


if __name__ == "__main__":
    print("Header date (ET):", header_date())
    print("ISO (ET)        :", iso_et())
    warn = sanity_check()
    print("Guard           :", warn or "ok — ET and UTC agree right now")
