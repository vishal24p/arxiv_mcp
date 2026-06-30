# arxiv-mcp

An [MCP](https://modelcontextprotocol.io) server that lets any coding agent
search arXiv and download papers. Free, no API key, two tools.

## Tools

| Tool | What it does |
| --- | --- |
| `search_arxiv(query, max_results=10)` | Free-text search. Returns title, authors, abstract, date, PDF URL. No PDF parsing. |
| `download_paper(arxiv_id)` | Streams a PDF into `./papers/<id>.pdf`. Idempotent. |

Both are read-only on the network side. The server touches arXiv's public
API (`export.arxiv.org`) — no key, no signup, no rate-limit token.

## Install

```bash
git clone https://github.com/vishal24p/arxiv_mcp.git
cd arxiv_mcp
uv venv
uv pip install -e .
```

Requires Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

## Wire it into your agent

The `arxiv-mcp` script is installed into the venv at `.venv\Scripts\`
(Windows) or `.venv/bin/` (macOS/Linux). Activate first, or call it by
path:

```bash
# Activate (then `arxiv-mcp` is on PATH)
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

arxiv-mcp install                # auto-detect and patch all found agents
arxiv-mcp install --only codex   # one specific agent
arxiv-mcp install --dry-run      # show what would change, write nothing
```

If you skip activation, invoke the executable directly:

```bash
# Windows
.venv\Scripts\arxiv-mcp.exe install
# macOS / Linux
.venv/bin/arxiv-mcp install
```

Supported agents:

| Agent | Config file | Format |
| --- | --- | --- |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | JSON |
| Claude Code | `~/.claude.json` | JSON |
| Cursor | `~/.cursor/mcp.json` | JSON |
| Codex CLI | `~/.codex/config.toml` | TOML |

The installer merges an `arxiv` entry into each detected config, backs up
the original to `<file>.bak`, and never touches other settings. It is
idempotent — re-running with the same flag reports the entry already
exists and writes nothing. Restart the agent and the tools appear.

## Use

Ask the agent anything that needs arXiv:

```
find 3 papers on mixture of experts
download 1706.03762
what's the most cited recent paper on RLHF?
```

The agent picks `search_arxiv` or `download_paper` based on what you ask.
PDFs land in `./papers/`. Override the location with
`ARXIV_MCP_PAPERS_DIR`.

## Run without installing to an agent

```bash
arxiv-mcp serve
# ...or:
python -m arxiv_mcp
```

Speaks MCP over stdio. Useful for testing or wiring into something that
isn't a coding agent.

## Troubleshooting

**`arxiv-mcp` is not recognized as the name of a cmdlet / command**

The script lives in the venv at `.venv\Scripts\arxiv-mcp.exe` (Windows)
or `.venv/bin/arxiv-mcp` (macOS/Linux). It is only on `PATH` while the
venv is active. Either activate the venv first, or invoke the
executable by its full path (see *Wire it into your agent* above).

The script name uses a hyphen (`arxiv-mcp`), not an underscore
(`arxiv_mcp`). The Python package is `arxiv_mcp`; the console script is
`arxiv-mcp`.

**Re-running `arxiv-mcp install` reports the entry already exists**

That is the intended idempotent behavior. Backups are at
`<config>.bak` next to each original file. To force a fresh install,
delete the `arxiv` key from the relevant config and re-run.

## License

Apache 2.0.
