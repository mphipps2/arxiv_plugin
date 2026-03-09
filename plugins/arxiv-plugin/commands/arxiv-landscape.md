---
description: "Generate a comprehensive research landscape analysis for a topic"
argument-hint: "<topic> [lookback-days, default 30] [--deep-dive]"
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
- **--deep-dive** (optional flag): If present, fetch full PDF text for 5-10 key papers and produce deeper analysis.

Parse the argument: strip `--deep-dive` flag if present, then if the last remaining token is a number, use it as lookback days and the rest as the topic.

## Steps

### 1. Read config & compute dates

Use Read to load `${CLAUDE_PLUGIN_ROOT}/config.yaml` to get categories and institutions.

Calculate `date_from` as today minus lookback days, `date_to` as yesterday.

**Output directory:** Determine a writable location for output and pass it via `--output-dir` to the generator script.

### 2. Spawn 4 subagents in parallel (Phase 1: Wide Scan)

Launch ALL FOUR agents in a single message so they run concurrently:

- **recent-papers-analyst**: "Search for recent papers on '{topic}' from {date_from} to {date_to}. Return JSON with recent_papers, themes, and publication_velocity."
- **institution-mapper**: "Map institutional activity for '{topic}' from {date_from} to {date_to}. Check these institutions: {institutions from config}. Return JSON with institutions array."
- **foundational-work-analyst**: "Find foundational and key papers on '{topic}'. Return JSON with key_papers array."
- **methodology-analyst**: "Analyze methodologies in '{topic}' research from {date_from} to {date_to}. Return JSON with methodologies array."

### 3. Collect results

Parse the JSON output from each subagent.

### 4. Deep dive (ONLY if `--deep-dive` flag is present)

Skip this entire step if `--deep-dive` was not specified.

#### 4a. Select papers for deep analysis

Review all 4 subagent results and select 5-10 papers for full-text analysis. Deduplicate by arXiv ID. Only include papers that have an arXiv ID.

Selection criteria:
- **Top 2-3 foundational papers**: Highest `citation_count` from `key_papers` that have an arXiv ID
- **Top 3-4 recent papers**: Highest `relevance_score` from `recent_papers`
- **1-2 methodology exemplars**: Pick a paper from `recent_papers` that represents the top "rising" methodology

#### 4b. Fetch full text (parallel)

For each selected paper, run in parallel (all Bash calls in a single message):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_paper.py --id <arxiv_id> --pdf-text --max-pages 10
```

Use `--max-pages 10` to keep text manageable (vs 20 for the report command).

#### 4c. Analyze full text

Process the fetched papers in batches of 3. For each batch:
1. Read the fetch output (which includes `pdf_text`)
2. For each paper, write a focused analysis covering:
   - **key_contributions**: 2-3 specific technical contributions from the full text (not just restating the abstract — look for architecture details, algorithms, theoretical results)
   - **methodology_details**: Specific techniques, model sizes, training procedures, datasets
   - **quantitative_results**: Key benchmark numbers, ablation results, comparisons to baselines
   - **connections**: How this paper relates to others in the landscape
3. Discard the raw PDF text before processing the next batch (to manage context)

For papers where PDF extraction failed, note that only abstract-level analysis was possible.

### 5. Synthesize executive summary

Based on all subagent results (and deep-dive findings if available), write the executive summary:

**Without `--deep-dive`:** 2-3 paragraphs covering the current state of research, key institutional players, dominant/emerging methodologies, notable recent developments.

**With `--deep-dive`:** 3-4 paragraphs. Add a paragraph with insights only discoverable from full text — specific benchmark numbers, architectural choices, training details that reveal where the field is actually heading vs. what abstracts claim.

### 6. Assemble landscape JSON and generate HTML

```json
{
  "topic": "...",
  "date_range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "executive_summary": "...",
  "recent_papers": [...from recent-papers-analyst...],
  "institutions": [...from institution-mapper...],
  "methodologies": [...from methodology-analyst...],
  "key_papers": [...from foundational-work-analyst...],
  "deep_dives": [
    {
      "id": "arXiv ID",
      "title": "...",
      "authors": ["..."],
      "selection_reason": "foundational | recent_top | methodology_exemplar",
      "key_contributions": "...",
      "methodology_details": "...",
      "quantitative_results": "...",
      "connections": "...",
      "pdf_url": "...",
      "arxiv_url": "..."
    }
  ]
}
```

If `--deep-dive` was not used, set `deep_dives` to an empty array `[]`.

Write the JSON to a temp file and pipe it to the generator:
```bash
cat /tmp/landscape_data.json | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_landscape.py --output-dir OUTPUT_DIR
```

### 7. Report

Tell the user the path to the generated HTML file and provide a brief overview of findings.
