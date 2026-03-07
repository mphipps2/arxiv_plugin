---
description: "Generate a comprehensive research landscape analysis for a topic"
argument-hint: "<topic> [lookback-days, default 30]"
allowed-tools:
  - mcp__plugin_arxiv-plugin_arxiv__search_papers
  - mcp__plugin_arxiv-plugin_arxiv__get_paper
  - mcp__plugin_arxiv-plugin_arxiv__get_daily_papers
  - mcp__plugin_arxiv-plugin_arxiv__enrich_institutions
  - mcp__plugin_arxiv-plugin_arxiv__search_by_institution
  - WebFetch
  - Bash
  - Read
  - Task
model: sonnet
---

Generate a comprehensive research landscape analysis for a topic.

## Arguments

- **topic** (required): The research topic to analyze (e.g., "attention mechanisms", "diffusion models").
- **lookback-days** (optional, default 30): Number of days to look back for recent papers.

Parse the argument: if the last token is a number, use it as lookback days and the rest as the topic.

## Steps

1. **Read config**: Use Read to load `${CLAUDE_PLUGIN_ROOT}/config.yaml` to get categories and institutions.

2. **Compute date range**: Calculate `date_from` as today minus lookback days, `date_to` as today.

3. **Spawn 4 subagents in parallel** using the Task tool with subagent_type set to the agent names. Launch ALL FOUR in a single message so they run concurrently:

   - **recent-papers-analyst**: "Search for recent papers on '{topic}' from {date_from} to {date_to}. Return JSON with recent_papers, themes, and publication_velocity."
   - **institution-mapper**: "Map institutional activity for '{topic}' from {date_from} to {date_to}. Check these institutions: {institutions from config}. Return JSON with institutions array."
   - **foundational-work-analyst**: "Find foundational and key papers on '{topic}'. Return JSON with key_papers array."
   - **methodology-analyst**: "Analyze methodologies in '{topic}' research from {date_from} to {date_to}. Return JSON with methodologies array."

4. **Collect results**: Parse the JSON output from each subagent.

5. **Synthesize executive summary**: Based on all four results, write a 2-3 paragraph executive summary covering:
   - The current state of research on the topic
   - Key institutional players
   - Dominant and emerging methodologies
   - Notable recent developments

6. **Assemble landscape JSON**:
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

7. **Generate HTML**: Pipe the JSON to the generator:
```bash
echo '<json_string>' | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_landscape.py
```

8. **Report**: Tell the user the path to the generated HTML file and provide a brief overview of findings.
