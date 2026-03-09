---
description: "Generate a comprehensive research landscape analysis for a topic"
argument-hint: "<topic> [lookback-days, default 30]"
allowed-tools:
  - Agent
  - Bash
  - Read
model: sonnet
---

Generate a comprehensive research landscape analysis for a topic.

## Arguments

- **topic** (required): The research topic to analyze (e.g., "attention mechanisms", "diffusion models").
- **lookback-days** (optional, default 30): Number of days to look back for recent papers.

Parse the argument: if the last token is a number, use it as lookback days and the rest as the topic.

## Steps

### 1. Read config & compute dates

Use Read to load `${CLAUDE_PLUGIN_ROOT}/config.yaml` to get categories and institutions.

Calculate `date_from` as today minus lookback days, `date_to` as yesterday.

**Output directory:** Determine a writable location for output and pass it via `--output-dir` to the generator script.

### 2. Spawn 4 subagents in parallel

Launch ALL FOUR agents in a single message so they run concurrently:

- **recent-papers-analyst**: "Search for recent papers on '{topic}' from {date_from} to {date_to}. Return JSON with recent_papers, themes, and publication_velocity."
- **institution-mapper**: "Map institutional activity for '{topic}' from {date_from} to {date_to}. Check these institutions: {institutions from config}. Return JSON with institutions array."
- **foundational-work-analyst**: "Find foundational and key papers on '{topic}'. Return JSON with key_papers array."
- **methodology-analyst**: "Analyze methodologies in '{topic}' research from {date_from} to {date_to}. Return JSON with methodologies array."

### 3. Collect results

Parse the JSON output from each subagent.

### 4. Synthesize executive summary

Based on all four results, write a 2-3 paragraph executive summary covering:
- The current state of research on the topic
- Key institutional players
- Dominant and emerging methodologies
- Notable recent developments

### 5. Assemble landscape JSON and generate HTML

```json
{
  "topic": "...",
  "date_range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "executive_summary": "...",
  "recent_papers": [...from recent-papers-analyst...],
  "institutions": [...from institution-mapper...],
  "methodologies": [...from methodology-analyst...],
  "key_papers": [...from foundational-work-analyst...]
}
```

Write the JSON to a temp file and pipe it to the generator:
```bash
cat /tmp/landscape_data.json | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_landscape.py --output-dir OUTPUT_DIR
```

### 6. Report

Tell the user the path to the generated HTML file and provide a brief overview of findings.
