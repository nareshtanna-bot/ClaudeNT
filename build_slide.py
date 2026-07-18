"""Build the biotech portfolio 1-month performance slide.

Thin CLI wrapper — the actual logic lives in cowork_bridge/portfolio.py so
the same code can be driven from here, from the Cowork bridge MCP server,
or from the portfolio-slide skill.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cowork_bridge.portfolio import build_portfolio_slide

if __name__ == "__main__":
    print("Fetching price data...")
    out_path, data = build_portfolio_slide(
        days=30,
        out_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "Biotech_Portfolio_1Month.pptx"),
    )
    print(f"\nSaved: {out_path}")
