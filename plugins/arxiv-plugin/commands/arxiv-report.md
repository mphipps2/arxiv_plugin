---
description: "Generate a deep-dive analysis report for an arXiv paper"
argument-hint: "<arxiv-id or search query>"
allowed-tools:
  - mcp__plugin_arxiv-plugin_arxiv__get_paper
  - mcp__plugin_arxiv-plugin_arxiv__search_papers
  - Bash
  - Read
  - WebFetch
model: sonnet
---

Generate a deep-dive report on a specific arXiv paper.

## Arguments

The user provides either:
- An arXiv ID (e.g., "2301.07041")
- A search query to find a paper

## Steps

1. **Resolve paper**: If the argument looks like an arXiv ID (contains digits and dots, possibly with a version suffix like v1), call `get_paper` with it. Otherwise, call `search_papers` with the argument as a query (max_results=5), show the user the top results, and use the first result.

2. **Fetch PDF context**: Use WebFetch to read the paper's PDF URL to get additional context from the paper content. If WebFetch fails, proceed with the abstract alone.

3. **Analyze the paper**: Based on the abstract and any PDF content, produce an analysis with these fields:
   - **tldr**: A 1-2 sentence summary accessible to a technical audience.
   - **problem**: What problem does the paper address? Why is it important?
   - **approach**: What methodology or technique does the paper propose?
   - **results**: What are the key findings and how do they compare to prior work?
   - **limitations**: What are the acknowledged or apparent limitations?
   - **related_work**: What are the most relevant related papers or research directions?
   - **relevance**: Why might this paper matter to an AI/ML practitioner?

4. **Assemble report JSON**: Build a JSON object:
```json
{
  "paper": {"id": "...", "title": "...", "authors": [], "published": "...", "categories": [], "arxiv_url": "...", "pdf_url": "..."},
  "analysis": {"tldr": "...", "problem": "...", "approach": "...", "results": "...", "limitations": "...", "related_work": "...", "relevance": "..."}
}
```

5. **Generate HTML**: Pipe the JSON to the generator:
```bash
echo '<json_string>' | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py
```

6. **Report**: Tell the user the path to the generated HTML file and provide a brief summary of the paper.
