# Technical Design Record: arxiv-plugin

## Overview

A Claude Code plugin for arxiv-based research workflows. Provides an MCP server connecting to arXiv and OpenAlex APIs, with three command-driven skills for daily paper monitoring, paper deep-dives, and research landscape analysis.

## Architecture

### MCP Server (stdio, Python)

Single Python process communicating via stdin/stdout JSON-RPC. Connects to two external APIs:

- **arXiv API** — paper search, metadata, daily listings. Free, no key required. Rate limited (3s between requests).
- **OpenAlex API** — institution/affiliation enrichment, citation data. Free, no key required (polite pool via email header).

In-session caching layer to avoid redundant calls, especially for daily paper lists which are immutable once announced.

#### Tools

| Tool | Purpose | Parameters |
|------|---------|------------|
| `search_papers` | General arXiv query search | `query`, `categories` (list), `date_from`, `date_to`, `max_results`, `sort_by` |
| `get_daily_papers` | Papers announced on a given date | `date` (default: yesterday), `categories` (list) |
| `get_paper` | Full metadata for a single paper | `arxiv_id` |
| `enrich_institutions` | Add institution affiliations via OpenAlex | `arxiv_ids` (list) |
| `search_by_institution` | Papers from a specific organization | `institution`, `date_from`, `date_to`, `categories` |

### Configuration

`config.yaml` in plugin root, prepopulated with reasonable defaults:

```yaml
categories:
  - cs.AI
  - cs.LG
  - cs.CL
  - cs.CV
  - stat.ML

institutions:
  - OpenAI
  - Google DeepMind
  - Meta AI
  - Anthropic
  - Microsoft Research

output_dir: ./arxiv-output

openalex:
  email: null  # optional, for polite API pool
```

### Template Rendering

Scripts in `scripts/` take structured JSON (from MCP tool results + agent analysis) and produce self-contained HTML files using:

- **Jinja2** for templating with shared base layout
- **Tailwind CSS** (CDN) for styling
- **Chart.js** (CDN) for visualizations

Output written to `./arxiv-output/` with predictable naming:
- `dashboard-YYYY-MM-DD.html`
- `report-ARXIV_ID.html`
- `landscape-TOPIC-YYYY-MM-DD.html`

## Commands

### `/arxiv-dashboard`

Daily analytics dashboard showing what happened in configured research fields.

**Flow:**
1. Read `config.yaml` for default categories and institutions
2. Call `get_daily_papers` for each category via MCP
3. Call `enrich_institutions` on collected paper IDs
4. Assemble JSON payload with paper data, category counts, institution breakdown
5. Run `scripts/generate_dashboard.py` with JSON input
6. Output HTML artifact

**Dashboard sections:**
- Summary stats (total papers, per-category counts)
- Category breakdown bar chart
- Institution leaderboard with paper counts
- Highlighted/notable papers
- Filterable paper listing table (title, authors, categories, institution)

### `/arxiv-report`

Deep-dive report on a single paper.

**Flow:**
1. Accept arxiv ID (e.g., `2401.12345`) or search query as argument
2. Call `get_paper` via MCP for metadata
3. Claude reads the paper PDF directly via URL
4. Claude produces analysis sections as structured JSON
5. Run `scripts/generate_report.py` with JSON input
6. Output HTML artifact

**Report sections:**
- Paper metadata (title, authors, date, categories, arxiv link)
- TL;DR (2-3 sentence summary)
- Problem statement / motivation
- Approach / methodology
- Key results and contributions
- Limitations and open questions
- Related work context
- Relevance assessment

### `/arxiv-landscape`

Multi-subagent research landscape survey for a given topic.

**Flow:**
1. Accept topic query and optional lookback period (default: 30 days) as arguments
2. Spawn 4 subagents in parallel (see below)
3. Collect and synthesize subagent outputs
4. Run `scripts/generate_landscape.py` with combined JSON
5. Output HTML artifact

**Subagents:**

| Agent | Role | Tools Used |
|-------|------|------------|
| `recent-papers-analyst` | Survey recent work within lookback window | `search_papers`, `get_paper` |
| `institution-mapper` | Identify active institutions and their output | `search_by_institution`, `enrich_institutions` |
| `foundational-work-analyst` | Find seminal/highly-cited foundational papers | OpenAlex citation data, `get_paper` |
| `methodology-analyst` | Categorize approaches, identify trends | `search_papers`, `get_paper` |

**Landscape artifact sections:**
- Executive summary
- Recent papers timeline
- Institution activity heatmap
- Methodology taxonomy
- Key papers reference list

## Plugin Structure

```
arxiv-plugin/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── config.yaml
├── server/
│   ├── arxiv_mcp_server.py
│   └── requirements.txt          # arxiv, requests, mcp
├── scripts/
│   ├── generate_dashboard.py
│   ├── generate_report.py
│   ├── generate_landscape.py
│   ├── requirements.txt          # jinja2
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── report.html
│       ├── landscape.html
│       ├── charts.js
│       └── styles.css
├── agents/
│   ├── recent-papers-analyst.md
│   ├── institution-mapper.md
│   ├── foundational-work-analyst.md
│   └── methodology-analyst.md
└── commands/
    ├── arxiv-dashboard.md
    ├── arxiv-report.md
    └── arxiv-landscape.md
```

### MCP Configuration (`.mcp.json`)

```json
{
  "arxiv": {
    "command": "python",
    "args": ["${CLAUDE_PLUGIN_ROOT}/server/arxiv_mcp_server.py"],
    "env": {
      "PYTHONUNBUFFERED": "1"
    }
  }
}
```

### Plugin Manifest (`.claude-plugin/plugin.json`)

```json
{
  "name": "arxiv-plugin",
  "version": "0.1.0",
  "description": "arXiv research workflows: daily dashboards, paper reports, and landscape analysis",
  "author": "mike",
  "keywords": ["arxiv", "research", "papers", "dashboard", "academic"]
}
```

## External Dependencies

### Python (MCP Server)
- `arxiv` — arXiv API wrapper
- `requests` — OpenAlex API calls
- `mcp` — Model Context Protocol SDK

### Python (Scripts)
- `jinja2` — HTML template rendering

### CDN (Runtime, in generated HTML)
- Tailwind CSS
- Chart.js

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Institution data source | OpenAlex (not arXiv) | arXiv affiliations are optional free-form text, mostly missing. OpenAlex has 109k normalized institutions. |
| Single vs. dual MCP server | Single | arXiv and OpenAlex are tightly coupled for the institution enrichment use case. Simpler to maintain. |
| Template engine | Jinja2 | Mature, supports inheritance/loops/conditionals. Worth the dependency for shared base layouts. |
| Chart rendering | Chart.js via CDN | Prettier than inline SVG, Cowork artifact rendering supports CDN access. |
| PDF text extraction | None (Claude reads URL) | Avoids heavy dependency (pymupdf). Claude can read PDFs directly via URL. |
| Output format | Self-contained HTML files | Compatible with Cowork artifact rendering and browser viewing. |
| Config approach | `config.yaml` with defaults | Single source of truth, easy to edit, prepopulated so it works out of the box. |
| Landscape lookback | Configurable (default 30 days) | Different topics have different publication velocities. |
| Caching | In-session, in MCP server | Daily paper lists are immutable once announced. Avoids redundant API calls and respects arXiv rate limits. |
