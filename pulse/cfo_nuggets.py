#!/usr/bin/env python3
"""
cfo_nuggets.py — one CFO thing worth knowing, every evening.

GOAL: the Evening Pulse should teach you one durable CFO/finance idea per day,
so the two pulses alone keep you moving toward the CFO seat. Nuggets are
anchored to your world — gene-editing peers (DTIL/PRME/BEAM/EDIT/CRSP/NTLA),
biotech capital markets, and the numbers a biotech CFO actually defends.

Rotation is DETERMINISTIC by ET day-of-year, so:
  • you never get the same nugget two days running,
  • the bank cycles cleanly (add more and the cycle just lengthens),
  • it's reproducible (re-running the same day gives the same nugget).

Usage:
  from cfo_nuggets import nugget_block
  evening_email += nugget_block()
"""
from pulse_dates import now_et

# Each nugget: (tag, headline, body). Keep bodies tight — one idea, one example.
NUGGETS = [
    ("RUNWAY", "Cash runway is the only clock that matters",
     "Runway = cash ÷ monthly net burn. A biotech CFO manages TO a data "
     "readout, not to a fiscal year — you want cash to clear the next "
     "value-inflection catalyst plus a buffer. If runway dips under ~12 "
     "months, the auditor forces 'going concern' language (ASC 205-40) into "
     "the 10-K, which itself spooks investors and raises your cost of capital."),
    ("DILUTION", "The 'baby shelf' rule quietly caps small-caps",
     "If public float < $75M, SEC rules (S-3 General Instruction I.B.6) limit "
     "you to selling 1/3 of that float in any rolling 12 months. So the very "
     "moment a beaten-down biotech most needs cash, its ability to raise on "
     "the shelf is throttled. Watch float vs. that $75M line like a hawk."),
    ("BURN", "Gross burn vs. net burn — know which one you're quoting",
     "Gross burn = total cash out the door. Net burn = gross minus cash in "
     "(collaboration payments, grants, interest income). DTIL's Lilly "
     "collaboration inflows reduce NET burn — so quoting gross makes runway "
     "look shorter than it is. On earnings calls, always say which you mean."),
    ("NON-GAAP", "Reg G: you can show non-GAAP, but GAAP comes first",
     "Regulation G requires any non-GAAP metric (e.g., 'cash used in "
     "operations ex-one-times') to be reconciled to the nearest GAAP figure, "
     "with GAAP given equal or greater prominence. Biotechs lean on non-GAAP "
     "R&D to strip stock-comp noise — legal, but the reconciliation is "
     "mandatory."),
    ("SBC", "Stock comp is a real expense that never touches cash",
     "ASC 718 runs option/RSU fair value through the P&L, inflating GAAP net "
     "loss — but it's non-cash, so you add it back on the cash-flow statement. "
     "For talent-heavy gene-editing shops, SBC can be 20–35% of opex. It's the "
     "#1 reason GAAP loss > actual cash burn."),
    ("R&D", "R&D is expensed, not capitalized — that's why biotechs 'lose' money",
     "Under ASC 730, R&D hits the income statement immediately; there's no "
     "asset to amortize later. A pre-revenue biotech spending $150M on trials "
     "shows a $150M loss even if the science is working. GAAP net loss ≠ "
     "failure — it's the accounting model for the whole sector."),
    ("606", "Milestone revenue can whipsaw the top line",
     "Under ASC 606, collaboration milestones are recognized only when it's "
     "'probable' a significant reversal won't occur — so a single achieved "
     "milestone can drop a lump of revenue into one quarter and none the next. "
     "Smooth-looking biotech revenue is rare; explain the lumpiness in MD&A."),
    ("8-K", "The 8-K Item number IS the headline",
     "Before reading a word, the Item tells the story: 1.01 material "
     "agreement, 2.02 earnings, 3.02 unregistered equity, 5.02 exec change, "
     "8.01 'other' (often clinical data via Reg FD). Skim EDGAR by Item number "
     "and you triage a peer's news in seconds."),
    ("ATM", "The ATM is the CFO's stealthiest lever",
     "An at-the-market program lets you dribble stock into the open market at "
     "prevailing prices — no roadshow, no discount, minimal signaling. The "
     "trade-off: continuous quiet dilution. Most clinical biotechs keep one "
     "armed under their shelf and tap it on strength."),
    ("PIPE", "A PIPE trades cheap capital for a discount + an overhang",
     "A private placement (filed as Form D, then an S-1 resale) raises fast "
     "from institutions when the public window is shut — but usually at a "
     "discount to market, and the resale registration creates a supply "
     "overhang. Great in a crisis, dilutive in the aftermath."),
    ("REVERSE-SPLIT", "A reverse split fixes the price, not the problem",
     "Nasdaq delists you if the bid stays under $1 for 30 straight days. A "
     "reverse split (say 1-for-15) instantly lifts the quote to cure "
     "compliance — DTIL has done this. It changes share count and optics, not "
     "market cap or the underlying burn. Investors know the difference."),
    ("WORKING-CAPITAL", "For biotech, 'working capital' really means accruals",
     "With little revenue, the swing item isn't receivables — it's accrued "
     "R&D. CROs bill in arrears, so you estimate trial costs incurred but not "
     "yet invoiced. Under-accrue and next quarter's 'true-up' surprises "
     "everyone. The clinical-accrual judgment is a signature biotech-CFO skill."),
    ("FPI", "Not every peer plays by 10-K rules",
     "CRISPR Therapeutics (CRSP) is Swiss-domiciled, so it files 20-F + 6-K, "
     "not 10-K/10-Q/8-K, and its insiders skip Section 16 (no Form 4). When you "
     "benchmark disclosures across peers, check the filer regime first — you're "
     "sometimes comparing apples to a different fruit entirely."),
    ("GUIDANCE", "Biotechs guide on runway, not EPS",
     "Sell-side won't model earnings for a pre-revenue name, so your guidance "
     "currency is 'cash runway into [quarter/year]' plus expected catalysts. "
     "Extending guided runway by a quarter — via burn control or non-dilutive "
     "cash — is often a bigger stock event than the science."),
    ("13D-G", "A 13D vs a 13G tells you who just showed up",
     "Both are filed by holders crossing 5% of YOUR stock. 13G = passive "
     "(index funds, long-only) — benign. 13D = active/activist intent — read "
     "every word. As CFO you monitor these for the cap table and brief the CEO "
     "when a 13D lands."),
    ("CRITICAL-AUDIT", "Critical Audit Matters flag where judgment lives",
     "Since 2019 the auditor must call out CAMs in the 10-K — the areas of "
     "highest judgment. For biotech it's almost always clinical-accrual "
     "estimates and going-concern. CAMs are a free roadmap to where your "
     "numbers are softest; read a peer's to learn where yours will be probed."),
    ("BURN-MULTIPLE", "Cheap capital hides a bad burn multiple",
     "Burn multiple = net burn ÷ net new value created (for biotech, proxy the "
     "denominator with pipeline progress/risk-adjusted NPV, not revenue). It "
     "reframes 'are we spending efficiently?' independent of a hot financing "
     "window. Discipline shows up here before it shows up in the stock."),
    ("DEFERRED-TAX", "Your NOLs are an asset you probably can't use yet",
     "Years of losses build big net operating loss carryforwards — a deferred "
     "tax asset. But if profits aren't 'more likely than not,' GAAP makes you "
     "park a full valuation allowance against it, so it shows ~$0 on the "
     "balance sheet. It becomes real only near profitability — or in an "
     "acquisition (subject to Section 382 limits)."),
    ("MD&A", "MD&A is where you get to tell the story",
     "The numbers are fixed; MD&A is your narrative — why burn moved, what a "
     "milestone means, how runway maps to catalysts. It's the most-read part "
     "of the 10-K/10-Q for a pre-revenue biotech. A CFO who writes MD&A well "
     "controls the framing before the sell-side does."),
    ("SECTION-16", "Insider trades post in 2 business days — plan around it",
     "Section 16 officers/directors must file Form 4 within 2 business days of "
     "any trade. 10b5-1 plans let insiders pre-schedule sales during blackouts "
     "with an affirmative defense — but the 2022 rules added cooling-off "
     "periods. As CFO you own this calendar for the whole exec team."),
]


def _pick(dt=None):
    dt = dt or now_et()
    return NUGGETS[dt.timetuple().tm_yday % len(NUGGETS)]


def nugget_block(dt=None) -> str:
    tag, head, body = _pick(dt)
    return (f"🎓 CFO NUGGET — {tag}\n{head}.\n{body}")


def nugget_html(dt=None) -> str:
    tag, head, body = _pick(dt)
    return (
        '<div style="background:#eef6f1;border-left:4px solid #0b3d2e;'
        'padding:12px 14px;border-radius:6px;margin:14px 0">'
        f'<div style="font-size:11px;font-weight:700;letter-spacing:.6px;'
        f'color:#0b6b4f">🎓 CFO NUGGET · {tag}</div>'
        f'<div style="font-weight:700;margin:3px 0 4px">{head}.</div>'
        f'<div style="font-size:14px;color:#33414d">{body}</div></div>')


if __name__ == "__main__":
    print(nugget_block())
    print(f"\n(bank: {len(NUGGETS)} nuggets · rotates by ET day-of-year, "
          "no repeat until the bank is exhausted)")
