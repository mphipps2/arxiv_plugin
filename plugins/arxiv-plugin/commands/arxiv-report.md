---
description: "Generate a deep-dive analysis report for an arXiv paper"
argument-hint: "<arxiv-id or search query>"
allowed-tools:
  - Bash
  - Read
model: sonnet
---

Generate a deep-dive report on a specific arXiv paper.

## Arguments

The user provides either:
- An arXiv ID (e.g., "2301.07041")
- A search query to find a paper

## Steps

### 1. Fetch paper metadata and PDF text (Bash)

If the argument looks like an arXiv ID (contains digits and dots, possibly with a version suffix like v1):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_paper.py --id <arxiv_id> --pdf-text
```

Otherwise, search by query:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_paper.py --query "<query>"
```

If searching by query, the script returns up to 5 results. Show the user the top results and then re-run with `--id` for the chosen paper plus `--pdf-text`.

The script outputs JSON with `papers` (array of paper metadata) and optionally `pdf_text` (extracted text from the first 20 pages of the PDF).

### 2. Analyze the paper

Based on the abstract AND the extracted PDF text (if available), produce an analysis with these fields:
- **tldr**: A 1-2 sentence summary accessible to a technical audience.
- **problem**: What problem does the paper address? Why is it important?
- **approach**: What methodology or technique does the paper propose?
- **results**: What are the key findings and how do they compare to prior work?
- **limitations**: What are the acknowledged or apparent limitations?
- **related_work**: What are the most relevant related papers or research directions?
- **relevance**: Why might this paper matter to an AI/ML practitioner?

When PDF text is available, use it to ground the analysis in specific details from the paper (architecture names, hyperparameters, ablation results, etc.) rather than inferring from the abstract alone. Be explicit about what comes from the paper vs. general knowledge.

### 3. Assemble report JSON and generate HTML

Build a JSON object:
```json
{
  "paper": {"id": "...", "title": "...", "authors": [], "published": "...", "categories": [], "arxiv_url": "...", "pdf_url": "..."},
  "analysis": {"tldr": "...", "problem": "...", "approach": "...", "results": "...", "limitations": "...", "related_work": "...", "relevance": "..."}
}
```

Write the JSON to a temp file and pipe it to the generator:
```bash
cat /tmp/arxiv_report_data.json | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py --output-dir OUTPUT_DIR
```

**Output directory:** Determine a writable location for output and pass it via `--output-dir`.

### 4. Report

Tell the user the path to the generated HTML file and provide a brief summary of the paper.
