# ClaudeNT — Portfolio Slide Builder + Cowork Bridge

Builds a one-slide biotech portfolio performance deck (DTIL · PRME · BEAM ·
EDIT · CRSP · NTLA by default) from live Yahoo Finance prices, and bridges
that capability into the Claude app — Cowork, Claude Desktop, claude.ai,
and mobile.

## What's here

| Path | What it is |
|---|---|
| `build_slide.py` | CLI: builds the 1-month deck (`Biotech_Portfolio_1Month.pptx`) |
| `cowork_bridge/portfolio.py` | The slide-builder library (parameterized tickers / window / title) |
| `cowork_bridge/server.py` | MCP server exposing the builder as tools (stdio + HTTP) |
| `.claude/skills/portfolio-slide/SKILL.md` | Agent Skill — auto-loaded by Cowork / Claude Code from this repo |

MCP tools exposed by the bridge:

- **`get_portfolio_performance`** `(tickers?, days?)` — returns per-ticker % return and latest close, no deck
- **`build_portfolio_slide`** `(tickers?, days?, title?)` — fetches prices and renders the full .pptx
- **`list_decks`** — lists decks already generated in the repo folder

## Setup

```bash
pip install -r cowork_bridge/requirements.txt
```

## Using it from the Claude app

### Option 1 — Cowork (Claude desktop app): use the skill (easiest)

Cowork loads project skills from `.claude/skills/` in the folder you open.
Just open this repo folder in a Cowork session and ask for your portfolio
slide — the `portfolio-slide` skill tells Claude how to run the builder.
Nothing to configure.

### Option 2 — Claude Desktop chat: local MCP server (stdio)

Claude Desktop launches local stdio MCP servers listed in its config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

(Open it via Settings → Developer → Edit Config.) Add:

```json
{
  "mcpServers": {
    "claudent-portfolio": {
      "command": "python",
      "args": ["/absolute/path/to/ClaudeNT/cowork_bridge/server.py"]
    }
  }
}
```

Restart the app and the three portfolio tools appear in chat.

> Note: Cowork itself does not pick up stdio servers from
> `claude_desktop_config.json` — for Cowork use the skill (Option 1) or a
> remote connector (Option 3).

### Option 3 — Cowork connectors / claude.ai / mobile: remote MCP (HTTP)

Cowork, claude.ai web, and the mobile app only talk to **remote** MCP
connectors. Run the bridge in HTTP mode and expose it at a public URL:

```bash
python cowork_bridge/server.py --http --port 8746
# then e.g.:  ngrok http 8746   (or cloudflared tunnel, or host it in the cloud)
```

Add the resulting URL (`https://<your-host>/mcp`) as a custom connector at
claude.ai → Settings → Connectors (Desktop: Customize → Connectors).
Connectors sync through your claude.ai account, so Cowork and mobile both
see it.

⚠️ The HTTP mode has no authentication built in — don't leave a tunnel to
it open to the public internet longer than you need it.

## CLI usage

```bash
python build_slide.py        # default 6-ticker portfolio, 30-day window
```

Custom runs:

```python
from cowork_bridge.portfolio import build_portfolio_slide
path, data = build_portfolio_slide(tickers=["DTIL", "CRSP"], days=90, title="Q2 Check-in")
```
