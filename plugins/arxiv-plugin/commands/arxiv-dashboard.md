---
description: "Generate a weekly AI engineering dashboard with curated picks, topic clustering, and relevance scoring"
argument-hint: "[lookback_days: N, default 7]"
allowed-tools:
  - Agent
  - Bash
  - Read
model: sonnet
---

Generate a weekly AI engineering dashboard that classifies papers by topic, scores relevance, and surfaces top picks.

## Arguments

The user may pass a number for `lookback_days` to override the config default (e.g. `/arxiv-dashboard 14` for two weeks).

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
- `continual-learning` — Continual / lifelong learning

**Retrieval & Knowledge**
- `rag-retrieval` — RAG architectures & retrieval methods
- `memory-replay` — Memory replay & external memory systems
- `structured-data` — Structured data / SQL / knowledge graphs

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
- `pretraining-scaling`, `rlhf-preference`, `fine-tuning`, `continual-learning` -> "Training & Optimization"
- `rag-retrieval`, `memory-replay`, `structured-data` -> "Retrieval & Knowledge"
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
- `continual-learning`: "Continual / lifelong learning"
- `rag-retrieval`: "RAG architectures & retrieval methods"
- `memory-replay`: "Memory replay & external memory systems"
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

### 1. Read config & compute dates

Use Read to load `${CLAUDE_PLUGIN_ROOT}/config.yaml`. Get `categories`, `lookback_days` (default 7), and `output_dir`.

Calculate `week_end` = yesterday's date and `week_start` = `week_end - lookback_days + 1`. If the user provided a custom lookback_days argument, use that instead of the config value.

**IMPORTANT:** The date range is `week_start` through `week_end` (yesterday). Do NOT include today's date — today's papers are still arriving and would produce incomplete results. Pass exactly these dates to both `fetch_papers.py` and `assemble_dashboard.py`.

### 2. Fetch papers (Bash)

Run the fetch script to download papers day-by-day, with automatic caching:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_papers.py \
  --config ${CLAUDE_PLUGIN_ROOT}/config.yaml \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD
```

This handles all caching logic: skips days already cached, always re-fetches today, re-fetches yesterday only on first run of the day.

### 3. Classify (parallel subagents)

Check which days in the date range still need classification by looking for missing files in `{output_dir}/cache/classified/YYYY-MM-DD.json`.

For each day that needs classification, spawn a `paper-classifier` agent (`${CLAUDE_PLUGIN_ROOT}/agents/paper-classifier.md`) using the Agent tool. Each agent receives:

```
Classify the papers in this file.
papers_path: {output_dir}/cache/papers/YYYY-MM-DD.json
output_path: {output_dir}/cache/classified/YYYY-MM-DD.json
```

**Launch all agents in parallel** (one per day). On repeat runs, most days are cached so only 1-2 agents are needed.

Skip days where the papers cache file has 0 papers — write an empty classification file instead:
```json
{"classified_papers": []}
```

Wait for all agents to complete before proceeding.

### 4. Assemble (Bash)

Run the assembly script to merge papers and classifications into the dashboard data structure:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/assemble_dashboard.py \
  --config ${CLAUDE_PLUGIN_ROOT}/config.yaml \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD
```

This outputs the path to the assembled JSON file.

### 5. Curate & narrate (LLM)

Use Read to load the assembled JSON file. Look at the `high_relevance_papers` array (typically 15-50 papers). If the array is very large (>100), focus on the first 50 for curation.

**Top picks:** Select 5-10 must-reads from the high-relevance papers. When ranking candidates, weight author and institutional prominence alongside technical merit:

- Papers from top labs (OpenAI, Google DeepMind, Anthropic, Meta AI, Microsoft Research, etc.) or well-known researchers in their field should be given a significant boost — these tend to have higher impact, better follow-through, and more community attention.
- A strong paper from a leading group should generally rank above an equally strong paper from an unknown group.
- However, genuinely breakthrough work from any institution still deserves a top pick slot.

For each pick, write a 1-2 sentence rationale explaining why this matters to an AI engineer. Include: id, title, authors, categories, pdf_url, arxiv_url, rationale, topic, group.

**Weekly narrative:** Write 2-3 paragraphs summarizing the week's key developments in AI/ML research. Mention specific papers and trends. Write for an AI engineer audience — focus on what's actionable and noteworthy.

Update the assembled JSON: set `top_picks` and `weekly_narrative` fields. Remove the `high_relevance_papers` field (it was only needed for curation). Write the updated JSON back to a temp file (e.g. `/tmp/weekly_dashboard_data.json`).

### 6. Render (Bash)

Pipe the final JSON to the generator script:

```bash
cat /tmp/weekly_dashboard_data.json | python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_weekly_dashboard.py
```

### 7. Report

Tell the user:
- The path to the generated HTML file
- Quick stats: total papers, high relevance count, number of top picks
- Mention that they can open the HTML file in a browser to explore the interactive dashboard
