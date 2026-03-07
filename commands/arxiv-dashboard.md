---
description: "Generate a daily arXiv dashboard with paper counts, category breakdowns, and institution leaderboard"
argument-hint: "[date: YYYY-MM-DD, default yesterday]"
allowed-tools:
  - mcp__plugin_arxiv-plugin_arxiv__get_daily_papers
  - mcp__plugin_arxiv-plugin_arxiv__enrich_institutions
  - Bash
  - Read
model: sonnet
---

Generate an arXiv daily dashboard for the given date.

## Arguments

The user may provide a date in YYYY-MM-DD format. If no date is provided, use yesterday's date.

## Steps

1. **Read config**: Use Read to load `${CLAUDE_PLUGIN_ROOT}/config.yaml` to get the list of categories and institutions.

2. **Fetch papers**: Call `get_daily_papers` with the target date and the categories from config.

3. **Enrich with institutions**: Take the arXiv IDs from the returned papers and call `enrich_institutions` with them (batch in groups of 20 if there are many papers).

4. **Assemble dashboard JSON**: Build a JSON object matching this schema:
```json
{
  "date": "YYYY-MM-DD",
  "total_papers": 83,
  "categories": [{"name": "cs.AI", "count": 45}],
  "institutions": [{"name": "OpenAI", "count": 12}],
  "papers": [{"id": "...", "title": "...", "authors": [], "categories": [], "institutions": [], "abstract": "...", "pdf_url": "..."}]
}
```

To build `categories`: count how many papers have each category.
To build `institutions`: aggregate institution names from the enrichment data, count papers per institution, sort descending.
For each paper, attach the institution names from the enrichment data.

5. **Generate HTML**: Pipe the JSON to the generator script:
```bash
echo '<json_string>' | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_dashboard.py
```

6. **Report**: Tell the user the path to the generated HTML file.
