import requests
import json
import time
import datetime
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io

TICKERS = ["DTIL", "PRME", "BEAM", "EDIT", "CRSP", "NTLA"]
COLORS = {
    "DTIL": "#1F6FEB",   # blue  (primary focus)
    "PRME": "#8957E5",
    "BEAM": "#3FB950",
    "EDIT": "#F78166",
    "CRSP": "#D29922",
    "NTLA": "#58A6FF",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

end_ts = int(time.time())
start_ts = end_ts - (32 * 24 * 3600)  # ~32 days to ensure 1 full month

def fetch_history(ticker):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?interval=1d&period1={start_ts}&period2={end_ts}"
    )
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    dates = [datetime.datetime.utcfromtimestamp(t).strftime("%b %d") for t in timestamps]
    return dates, closes

def fetch_current_price(ticker):
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    q = data["quoteResponse"]["result"][0]
    return q.get("regularMarketPrice", None), q.get("regularMarketChangePercent", None)

# --- Fetch data ---
print("Fetching price data...")
history = {}
perf = {}
current_prices = {}

for ticker in TICKERS:
    try:
        dates, closes = fetch_history(ticker)
        # Filter out None values
        valid = [(d, c) for d, c in zip(dates, closes) if c is not None]
        if len(valid) >= 2:
            dd, cc = zip(*valid)
            history[ticker] = (list(dd), list(cc))
            pct = ((cc[-1] - cc[0]) / cc[0]) * 100
            perf[ticker] = round(pct, 2)
            current_prices[ticker] = cc[-1]
            print(f"  {ticker}: {pct:+.2f}%  (${cc[-1]:.2f})")
        time.sleep(0.3)
    except Exception as e:
        print(f"  {ticker}: ERROR — {e}")
        perf[ticker] = None
        history[ticker] = None

# --- Build the chart image ---
fig, axes = plt.subplots(1, 1, figsize=(11, 5.2), facecolor="#0D1117")
ax = axes
ax.set_facecolor("#0D1117")

for ticker in TICKERS:
    if history[ticker] is None:
        continue
    dd, cc = history[ticker]
    # Normalize to % from day 1
    base = cc[0]
    norm = [(c / base - 1) * 100 for c in cc]
    lw = 2.5 if ticker == "DTIL" else 1.5
    ax.plot(range(len(dd)), norm, color=COLORS[ticker], linewidth=lw,
            label=ticker, zorder=3 if ticker == "DTIL" else 2)

ax.axhline(0, color="#444C56", linewidth=0.8, linestyle="--", zorder=1)
ax.set_xticks([])
ax.set_ylabel("Return (%)", color="#8B949E", fontsize=9)
ax.tick_params(colors="#8B949E", labelsize=8)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_color("#30363D")
ax.spines["left"].set_color("#30363D")
ax.yaxis.label.set_color("#8B949E")
plt.setp(ax.get_yticklabels(), color="#8B949E")

legend = ax.legend(
    loc="upper left", frameon=True, fancybox=False,
    framealpha=0.3, edgecolor="#30363D",
    labelcolor="white", fontsize=8.5, ncol=3,
)
legend.get_frame().set_facecolor("#161B22")

ax.set_title("", pad=0)
fig.tight_layout(pad=1.2)

chart_buf = io.BytesIO()
fig.savefig(chart_buf, format="png", dpi=150, bbox_inches="tight",
            facecolor="#0D1117")
plt.close(fig)
chart_buf.seek(0)

# --- Build scoreboard bar chart ---
sorted_tickers = sorted([t for t in TICKERS if perf[t] is not None],
                        key=lambda t: perf[t])

fig2, ax2 = plt.subplots(figsize=(5.5, 3.5), facecolor="#0D1117")
ax2.set_facecolor("#0D1117")

bar_colors = [("#3FB950" if perf[t] >= 0 else "#F78166") for t in sorted_tickers]
bars = ax2.barh(sorted_tickers, [perf[t] for t in sorted_tickers],
                color=bar_colors, height=0.55, zorder=3)

for bar, ticker in zip(bars, sorted_tickers):
    val = perf[ticker]
    xpos = bar.get_width() + (0.3 if val >= 0 else -0.3)
    ha = "left" if val >= 0 else "right"
    ax2.text(xpos, bar.get_y() + bar.get_height() / 2,
             f"{val:+.1f}%", va="center", ha=ha,
             color="white", fontsize=9, fontweight="bold")

ax2.axvline(0, color="#444C56", linewidth=0.8)
ax2.set_xlabel("1-Month Return (%)", color="#8B949E", fontsize=8)
ax2.tick_params(colors="white", labelsize=9)
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
ax2.spines["bottom"].set_color("#30363D")
ax2.spines["left"].set_color("#30363D")
plt.setp(ax2.get_xticklabels(), color="#8B949E")
ax2.set_facecolor("#0D1117")
fig2.tight_layout(pad=1.0)

bar_buf = io.BytesIO()
fig2.savefig(bar_buf, format="png", dpi=150, bbox_inches="tight",
             facecolor="#0D1117")
plt.close(fig2)
bar_buf.seek(0)

# --- Build PowerPoint ---
prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

slide_layout = prs.slide_layouts[6]  # blank
slide = prs.slides.add_slide(slide_layout)

def set_bg(slide, hex_color):
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor.from_string(hex_color.lstrip("#"))

set_bg(slide, "0D1117")

def add_text(slide, text, left, top, width, height, font_size, bold=False,
             color="FFFFFF", align=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top),
                                      Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    return txBox

# Title
add_text(slide, "Biotech Portfolio — 1-Month Performance",
         0.3, 0.15, 9, 0.55, 22, bold=True, color="E6EDF3")

# Subtitle / date range
today = datetime.date.today()
month_ago = today - datetime.timedelta(days=30)
subtitle = f"{month_ago.strftime('%b %d')} – {today.strftime('%b %d, %Y')}  |  DTIL · PRME · BEAM · EDIT · CRSP · NTLA"
add_text(slide, subtitle, 0.3, 0.72, 12, 0.35, 9, color="8B949E")

# Thin separator line
from pptx.util import Pt as PtU
from pptx.oxml.ns import qn
line = slide.shapes.add_shape(
    1,  # MSO_SHAPE_TYPE.RECTANGLE
    Inches(0.3), Inches(1.08), Inches(12.73), Inches(0.02)
)
line.fill.solid()
line.fill.fore_color.rgb = RGBColor(0x21, 0x26, 0x2D)
line.line.fill.background()

# Line chart (left, large)
slide.shapes.add_picture(chart_buf, Inches(0.3), Inches(1.15),
                         Inches(7.8), Inches(4.0))

# Bar chart (right)
slide.shapes.add_picture(bar_buf, Inches(8.25), Inches(1.15),
                         Inches(4.8), Inches(3.8))

# Scorecards row at bottom
card_w = 2.0
card_h = 0.75
start_x = 0.3
card_y = 5.6

for i, ticker in enumerate(TICKERS):
    x = start_x + i * (card_w + 0.15)
    # Card background
    card = slide.shapes.add_shape(
        1, Inches(x), Inches(card_y), Inches(card_w), Inches(card_h)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(0x16, 0x1B, 0x22)
    card.line.color.rgb = RGBColor(0x30, 0x36, 0x3D)

    # Ticker label
    add_text(slide, ticker, x + 0.1, card_y + 0.04, card_w - 0.2, 0.3,
             10, bold=True, color="E6EDF3")

    if perf.get(ticker) is not None:
        pct = perf[ticker]
        price = current_prices.get(ticker, 0)
        pct_color = "3FB950" if pct >= 0 else "F78166"
        sign = "+" if pct >= 0 else ""
        add_text(slide, f"{sign}{pct:.2f}%",
                 x + 0.1, card_y + 0.33, card_w - 0.2, 0.28,
                 13, bold=True, color=pct_color)
        add_text(slide, f"${price:.2f}",
                 x + 1.1, card_y + 0.37, 0.8, 0.28,
                 9, bold=False, color="8B949E", align=PP_ALIGN.RIGHT)
    else:
        add_text(slide, "N/A", x + 0.1, card_y + 0.33, card_w - 0.2, 0.28,
                 11, bold=True, color="8B949E")

# Footer
add_text(slide,
         "Source: Yahoo Finance  |  For internal use only — not for distribution",
         0.3, 7.1, 12.73, 0.3, 7.5, color="444C56", align=PP_ALIGN.CENTER)

out_path = "/home/user/ClaudeNT/Biotech_Portfolio_1Month.pptx"
prs.save(out_path)
print(f"\nSaved: {out_path}")
