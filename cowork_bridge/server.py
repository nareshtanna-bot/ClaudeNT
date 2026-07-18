"""Cowork bridge — MCP server for the ClaudeNT portfolio slide builder.

Runs as a local stdio MCP server so the Claude desktop app (including
Cowork sessions) can fetch portfolio performance and build the PowerPoint
deck on demand.

Transports:
    python cowork_bridge/server.py           # stdio (Claude Desktop "Code"/chat via claude_desktop_config.json)
    python cowork_bridge/server.py --http    # streamable HTTP on port 8746 (host or
                                             # tunnel it, then add as a custom
                                             # connector for Cowork / mobile / web)
"""

import argparse
import glob
import os
import sys

# Allow running as a plain script (python cowork_bridge/server.py) without
# requiring the repo root on PYTHONPATH.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

from cowork_bridge import portfolio

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mcp = FastMCP(
    "ClaudeNT Portfolio Bridge",
    instructions=(
        "Bridge to the ClaudeNT biotech portfolio slide builder. "
        "Use get_portfolio_performance for quick numbers, and "
        "build_portfolio_slide to render the full PowerPoint deck. "
        f"The default portfolio is {', '.join(portfolio.DEFAULT_TICKERS)}."
    ),
)


@mcp.tool()
def get_portfolio_performance(tickers: list[str] | None = None, days: int = 30) -> dict:
    """Fetch current performance for the portfolio without building a deck.

    Args:
        tickers: Stock tickers to include. Defaults to the standard biotech
            portfolio (DTIL, PRME, BEAM, EDIT, CRSP, NTLA).
        days: Lookback window in days (default 30).

    Returns per-ticker percent return over the window, latest close price,
    and any per-ticker fetch errors.
    """
    data = portfolio.fetch_performance(tickers, days, log=lambda *_: None)
    return {
        "tickers": data["tickers"],
        "days": data["days"],
        "returns_pct": data["perf"],
        "latest_close": {t: round(p, 2) for t, p in data["current_prices"].items()},
        "errors": data["errors"],
    }


@mcp.tool()
def build_portfolio_slide(
    tickers: list[str] | None = None,
    days: int = 30,
    title: str | None = None,
) -> dict:
    """Build the portfolio performance PowerPoint deck and save it in the repo.

    Fetches fresh prices from Yahoo Finance, renders the normalized-return
    line chart, the return scoreboard, and per-ticker scorecards, and saves
    a widescreen .pptx.

    Args:
        tickers: Stock tickers to include. Defaults to the standard biotech
            portfolio (DTIL, PRME, BEAM, EDIT, CRSP, NTLA). Scorecards show
            the first six tickers; the first ticker is visually emphasized.
        days: Lookback window in days (default 30).
        title: Optional slide title override.
    """
    out_path, data = portfolio.build_portfolio_slide(
        tickers=tickers, days=days, title=title, log=lambda *_: None
    )
    return {
        "output_path": out_path,
        "returns_pct": data["perf"],
        "errors": data["errors"],
    }


@mcp.tool()
def list_decks() -> list[dict]:
    """List PowerPoint decks already generated in the repo folder."""
    decks = []
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "*.pptx"))):
        stat = os.stat(path)
        decks.append({
            "path": path,
            "size_bytes": stat.st_size,
            "modified": __import__("datetime").datetime.fromtimestamp(
                stat.st_mtime
            ).isoformat(timespec="seconds"),
        })
    return decks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClaudeNT Cowork bridge MCP server")
    parser.add_argument("--http", action="store_true",
                        help="serve streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8746)
    args = parser.parse_args()

    if args.http:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
