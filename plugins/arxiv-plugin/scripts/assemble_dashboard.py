#!/usr/bin/env python3
"""Assemble dashboard JSON from cached paper and classification data.

Usage:
    python assemble_dashboard.py --config config.yaml --start-date 2026-03-01 --end-date 2026-03-07
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import yaml

# --- Taxonomy (mirrors arxiv-dashboard.md) ---

TOPIC_TO_GROUP = {
    "long-context-memory": "Model Architecture & Capabilities",
    "multimodal": "Model Architecture & Capabilities",
    "reasoning-cot": "Model Architecture & Capabilities",
    "small-efficient": "Model Architecture & Capabilities",
    "pretraining-scaling": "Training & Optimization",
    "rlhf-preference": "Training & Optimization",
    "fine-tuning": "Training & Optimization",
    "continual-learning": "Training & Optimization",
    "rag-retrieval": "Retrieval & Knowledge",
    "memory-replay": "Retrieval & Knowledge",
    "structured-data": "Retrieval & Knowledge",
    "robustness-redteam": "Safety & Reliability",
    "hallucination": "Safety & Reliability",
    "uncertainty-calibration": "Safety & Reliability",
    "code-swe": "Applications",
    "scientific-domain": "Applications",
    "synthetic-data": "Applications",
    "multi-agent": "Emerging",
    "llm-judge": "Emerging",
    "world-models": "Emerging",
    "other": "Other",
}

TOPIC_LABELS = {
    "long-context-memory": "Long context / memory architectures",
    "multimodal": "Multimodality (vision-language, audio, video)",
    "reasoning-cot": "Reasoning & chain-of-thought / inference-time compute scaling",
    "small-efficient": "Small/efficient models (quantization, distillation, MoE)",
    "pretraining-scaling": "Pretraining data curation & scaling laws",
    "rlhf-preference": "RLHF / RLAIF / preference learning",
    "fine-tuning": "Fine-tuning methods (LoRA, PEFT, instruction tuning)",
    "continual-learning": "Continual / lifelong learning",
    "rag-retrieval": "RAG architectures & retrieval methods",
    "memory-replay": "Memory replay & external memory systems",
    "structured-data": "Structured data / SQL / tabular reasoning",
    "robustness-redteam": "Robustness, jailbreaks & red-teaming",
    "hallucination": "Hallucination detection & mitigation",
    "uncertainty-calibration": "Uncertainty quantification / calibration",
    "code-swe": "Code generation & software engineering agents",
    "scientific-domain": "Scientific discovery / domain-specific models",
    "synthetic-data": "Synthetic data generation",
    "multi-agent": "Multi-agent systems",
    "llm-judge": "LLM-as-judge / AI-assisted evaluation",
    "world-models": "World models & planning",
    "other": "Other",
}

GROUP_ORDER = [
    ("Model Architecture & Capabilities", ["long-context-memory", "multimodal", "reasoning-cot", "small-efficient"]),
    ("Training & Optimization", ["pretraining-scaling", "rlhf-preference", "fine-tuning", "continual-learning"]),
    ("Retrieval & Knowledge", ["rag-retrieval", "memory-replay", "structured-data"]),
    ("Safety & Reliability", ["robustness-redteam", "hallucination", "uncertainty-calibration"]),
    ("Applications", ["code-swe", "scientific-domain", "synthetic-data"]),
    ("Emerging", ["multi-agent", "llm-judge", "world-models"]),
    ("Other", ["other"]),
]

RELEVANCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def main():
    parser = argparse.ArgumentParser(description="Assemble dashboard JSON")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output-dir", help="Output directory (overrides config)")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    output_dir = Path(args.output_dir) if args.output_dir else Path(config.get("output_dir", "./arxiv-output"))
    papers_dir = output_dir / "cache" / "papers"
    classified_dir = output_dir / "cache" / "classified"

    start = datetime.strptime(args.start_date, "%Y-%m-%d")
    end = datetime.strptime(args.end_date, "%Y-%m-%d")

    # Load all papers and classifications
    all_papers = {}  # id -> paper dict
    classification_map = {}  # id -> {topic, group, relevance}
    papers_per_day = []

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")

        # Load papers for this day
        papers_file = papers_dir / f"{date_str}.json"
        day_count = 0
        if papers_file.exists():
            day_data = json.loads(papers_file.read_text())
            for p in day_data.get("papers", []):
                all_papers[p["id"]] = p
                day_count += 1

        # Load classifications for this day
        classified_file = classified_dir / f"{date_str}.json"
        if classified_file.exists():
            cls_data = json.loads(classified_file.read_text())
            for cp in cls_data.get("classified_papers", []):
                classification_map[cp["id"]] = {
                    "topic": cp["topic"],
                    "group": cp["group"],
                    "relevance": cp["relevance"],
                }

        papers_per_day.append({"date": date_str, "count": day_count})
        current += timedelta(days=1)

    # Merge papers with classifications
    for pid, paper in all_papers.items():
        cls = classification_map.get(pid, {"topic": "other", "group": "Other", "relevance": "low"})
        paper["topic"] = cls["topic"]
        paper["group"] = cls["group"]
        paper["relevance"] = cls["relevance"]

    # Build topic_groups
    topic_papers = {}  # topic_id -> [papers]
    for paper in all_papers.values():
        topic_papers.setdefault(paper["topic"], []).append(paper)

    topic_groups = []
    for group_name, topic_ids in GROUP_ORDER:
        topics = []
        group_total = 0
        for tid in topic_ids:
            papers = topic_papers.get(tid, [])
            papers.sort(key=lambda p: RELEVANCE_ORDER.get(p["relevance"], 2))
            high_count = sum(1 for p in papers if p["relevance"] == "high")
            topics.append({
                "id": tid,
                "label": TOPIC_LABELS[tid],
                "paper_count": len(papers),
                "high_relevance_count": high_count,
                "papers": papers,
            })
            group_total += len(papers)
        topic_groups.append({
            "name": group_name,
            "total_papers": group_total,
            "topics": topics,
        })

    # Sort groups by total_papers descending, "Other" always last
    other_group = [g for g in topic_groups if g["name"] == "Other"]
    non_other = [g for g in topic_groups if g["name"] != "Other"]
    non_other.sort(key=lambda g: g["total_papers"], reverse=True)
    topic_groups = non_other + other_group

    # Build summary
    total = len(all_papers)
    high_count = sum(1 for p in all_papers.values() if p["relevance"] == "high")
    medium_count = sum(1 for p in all_papers.values() if p["relevance"] == "medium")
    low_count = sum(1 for p in all_papers.values() if p["relevance"] == "low")

    summary = {
        "total_papers": total,
        "high_relevance_count": high_count,
        "medium_relevance_count": medium_count,
        "low_relevance_count": low_count,
        "papers_per_day": papers_per_day,
    }

    # Build categories count
    cat_counter = Counter()
    for paper in all_papers.values():
        for cat in paper.get("categories", []):
            cat_counter[cat] += 1
    categories = [{"name": name, "count": count} for name, count in cat_counter.most_common()]

    # Extract high-relevance papers for LLM curation
    high_relevance_papers = [
        {
            "id": p["id"],
            "title": p["title"],
            "authors": p["authors"],
            "abstract": p["abstract"],
            "topic": p["topic"],
            "group": p["group"],
            "categories": p["categories"],
            "pdf_url": p["pdf_url"],
            "arxiv_url": p["arxiv_url"],
            "published": p["published"],
        }
        for p in all_papers.values()
        if p["relevance"] == "high"
    ]

    # Build output
    assembled = {
        "week_start": args.start_date,
        "week_end": args.end_date,
        "summary": summary,
        "weekly_narrative": "",
        "top_picks": [],
        "topic_groups": topic_groups,
        "categories": categories,
        "institutions": [],
        "high_relevance_papers": high_relevance_papers,
    }

    out_file = output_dir / "cache" / f"assembled-{args.end_date}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(assembled, indent=2))

    print(str(out_file.resolve()), file=sys.stderr)
    # Also print to stdout for piping
    print(str(out_file.resolve()))


if __name__ == "__main__":
    main()
