---
description: "Generate a weekly AI engineering dashboard with curated picks, topic clustering, and relevance scoring"
argument-hint: "[--institutions] [lookback_days: N, default from config]"
allowed-tools:
  - mcp__plugin_arxiv-plugin_arxiv__search_papers
  - mcp__plugin_arxiv-plugin_arxiv__enrich_institutions
  - WebFetch
  - Task
  - Bash
  - Read
model: sonnet
---

Generate a weekly AI engineering dashboard that classifies papers by topic, scores relevance, and surfaces top picks.

## Arguments

The user may pass:
- `--institutions` flag: if present, run institution enrichment (expensive, skipped by default)
- A number for `lookback_days` to override the config default (e.g. `/arxiv-dashboard 14` for two weeks)

## Topic Taxonomy

**Model Architecture & Capabilities**
- `long-context-memory` — Long context / memory architectures
- `multimodal` — Multimodality (vision-language, audio, video)
- `reasoning-cot` — Reasoning & chain-of-thought / inference-time compute scaling
- `small-efficient` — Small/efficient models (quantization, distillation, MoE)

**Training & Optimization**
- `pretraining-scaling` — Pretraining data curation & scaling laws
- `rlhf-preference` — RLHF / RLAIF / preference learning
- `fine-tuning` — Fine-tuning methods (LoRA, PEFT, instruction tuning)

**Retrieval & Knowledge**
- `rag-retrieval` — RAG architectures & retrieval methods
- `structured-data` — Structured data / SQL / tabular reasoning

**Safety & Reliability**
- `robustness-redteam` — Robustness, jailbreaks & red-teaming
- `hallucination` — Hallucination detection & mitigation
- `uncertainty-calibration` — Uncertainty quantification / calibration

**Applications**
- `code-swe` — Code generation & software engineering agents
- `scientific-domain` — Scientific discovery / domain-specific models
- `synthetic-data` — Synthetic data generation

**Emerging**
- `multi-agent` — Multi-agent systems
- `llm-judge` — LLM-as-judge / AI-assisted evaluation
- `world-models` — World models & planning

- `other` — Other

**Topic-to-Group Mapping:**
- `long-context-memory`, `multimodal`, `reasoning-cot`, `small-efficient` -> "Model Architecture & Capabilities"
- `pretraining-scaling`, `rlhf-preference`, `fine-tuning` -> "Training & Optimization"
- `rag-retrieval`, `structured-data` -> "Retrieval & Knowledge"
- `robustness-redteam`, `hallucination`, `uncertainty-calibration` -> "Safety & Reliability"
- `code-swe`, `scientific-domain`, `synthetic-data` -> "Applications"
- `multi-agent`, `llm-judge`, `world-models` -> "Emerging"
- `other` -> "Other"

**Topic Labels:**
- `long-context-memory`: "Long context / memory architectures"
- `multimodal`: "Multimodality (vision-language, audio, video)"
- `reasoning-cot`: "Reasoning & chain-of-thought / inference-time compute scaling"
- `small-efficient`: "Small/efficient models (quantization, distillation, MoE)"
- `pretraining-scaling`: "Pretraining data curation & scaling laws"
- `rlhf-preference`: "RLHF / RLAIF / preference learning"
- `fine-tuning`: "Fine-tuning methods (LoRA, PEFT, instruction tuning)"
- `rag-retrieval`: "RAG architectures & retrieval methods"
- `structured-data`: "Structured data / SQL / tabular reasoning"
- `robustness-redteam`: "Robustness, jailbreaks & red-teaming"
- `hallucination`: "Hallucination detection & mitigation"
- `uncertainty-calibration`: "Uncertainty quantification / calibration"
- `code-swe`: "Code generation & software engineering agents"
- `scientific-domain`: "Scientific discovery / domain-specific models"
- `synthetic-data`: "Synthetic data generation"
- `multi-agent`: "Multi-agent systems"
- `llm-judge`: "LLM-as-judge / AI-assisted evaluation"
- `world-models`: "World models & planning"
- `other`: "Other"

## Steps

### 1. Read config

Use Read to load `${CLAUDE_PLUGIN_ROOT}/config.yaml`. Get `categories`, `lookback_days` (default 7), and `output_dir`.

### 2. Compute date range

Calculate `week_end` = yesterday's date and `week_start` = `week_end - lookback_days + 1`. If the user provided a custom lookback_days argument, use that instead of the config value.

### 3. Fetch papers

**Primary method — MCP tool:**

Call `search_papers` with:
- `query`: `*`
- `categories`: the categories from config (as comma-separated string)
- `date_from`: week_start (YYYY-MM-DD)
- `date_to`: week_end (YYYY-MM-DD)
- `max_results`: 500
- `sort_by`: `submittedDate`

If the result contains exactly 500 papers (truncated), make a second call splitting the date range in half to get more complete results, then deduplicate by paper ID.

**Fallback — WebFetch (use if MCP tools fail, e.g. network restrictions):**

If `search_papers` fails or is unavailable, fetch papers directly from the arXiv API using `WebFetch`. Build the URL:

```
https://export.arxiv.org/api/query?search_query=(cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:stat.ML)+AND+submittedDate:[YYYYMMDD0000+TO+YYYYMMDD2359]&start=0&max_results=100&sortBy=submittedDate&sortOrder=descending
```

Replace the categories with those from config (joined with `+OR+`, each prefixed with `cat:`), and replace the date placeholders with `week_start` and `week_end` (formatted as YYYYMMDD, no dashes).

Use this prompt with WebFetch:
> Extract every paper entry as a JSON array. For each paper include these exact fields: id (just the arxiv id like "2603.05504v1"), title (full exact title), authors (array of name strings), abstract (the COMPLETE summary text verbatim — do NOT summarize or shorten it), published (the date string), categories (array of all category strings), pdf_url, arxiv_url. Return ONLY the JSON array, no other text.

Paginate by incrementing the `start` parameter by 100 until fewer than 100 results are returned. Merge all pages and deduplicate by paper ID.

### 4. Enrich institutions (ONLY if `--institutions` flag is present)

If the user passed `--institutions`, take the arXiv IDs from the returned papers and call `enrich_institutions` with them (batch in groups of 20). Otherwise, skip this step entirely — set `institutions` to an empty array `[]`.

### 5. Parallel classification

Split papers into batches of ~100 papers each. For each batch, create a Task using the `paper-classifier` agent (`${CLAUDE_PLUGIN_ROOT}/agents/paper-classifier.md`).

Pass each task a prompt containing:
- The batch of papers (for each paper include: id, title, abstract, categories)
- Instruction to classify per the taxonomy

Use TaskCreate to spawn all batch tasks in parallel. Then poll with TaskGet/TaskOutput until all complete.

Parse the JSON output from each classifier task. Merge all `classified_papers` arrays into a single list. Create a lookup map: `paper_id -> {topic, group, relevance}`.

### 6. Aggregate and curate

**Build topic_groups structure:**
For each group in order: "Model Architecture & Capabilities", "Training & Optimization", "Retrieval & Knowledge", "Safety & Reliability", "Applications", "Emerging", "Other":
- For each topic in that group, collect all papers classified under it
- For each paper, build the full paper object with: id, title, authors, categories, abstract, pdf_url, arxiv_url, relevance, published (date)
- Sort papers: high relevance first, then medium, then low
- Count: paper_count, high_relevance_count
- Omit topics with 0 papers from the output

Sort groups by total_papers descending, but always put "Other" last.

**Build summary:**
- total_papers: total count
- high_relevance_count, medium_relevance_count, low_relevance_count
- papers_per_day: for each date in the range, count papers published that day

**Build categories:** count papers per arXiv category, sort descending.

**Top picks:** Scan all papers with relevance "high". Select 5-10 must-reads. For each, write a 1-2 sentence rationale explaining why this matters to an AI engineer. Include: id, title, authors, categories, pdf_url, arxiv_url, rationale, topic, group.

**Weekly narrative:** Write 2-3 paragraphs summarizing the week's key developments in AI/ML research. Mention specific papers and trends. Write for an AI engineer audience — focus on what's actionable and noteworthy.

### 7. Assemble JSON and generate HTML

Build the full JSON object:
```json
{
  "week_start": "YYYY-MM-DD",
  "week_end": "YYYY-MM-DD",
  "summary": {
    "total_papers": N,
    "high_relevance_count": N,
    "medium_relevance_count": N,
    "low_relevance_count": N,
    "papers_per_day": [{"date": "YYYY-MM-DD", "count": N}]
  },
  "weekly_narrative": "...",
  "top_picks": [...],
  "topic_groups": [...],
  "categories": [...],
  "institutions": [...]
}
```

Pipe the JSON to the generator script:
```bash
echo '<json_string>' | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_weekly_dashboard.py
```

IMPORTANT: The JSON may be very large. Write it to a temporary file and pipe it:
```bash
cat /tmp/weekly_dashboard_data.json | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_weekly_dashboard.py
```

### 8. Report

Tell the user:
- The path to the generated HTML file
- Quick stats: total papers, high relevance count, number of top picks
- Mention that they can open the HTML file in a browser to explore the interactive dashboard
