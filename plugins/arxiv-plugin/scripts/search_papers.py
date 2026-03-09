#!/usr/bin/env python3
"""Search arXiv papers by topic with optional date range.

Usage:
    python search_papers.py --query "attention mechanisms" --max-results 50
    python search_papers.py --query "diffusion models" --date-from 2026-02-01 --date-to 2026-03-01
"""

import argparse
import json
import time

import arxiv

ARXIV_MIN_INTERVAL = 3.0
_last_call = 0.0


def _rate_limit():
    global _last_call
    now = time.monotonic()
    elapsed = now - _last_call
    if elapsed < ARXIV_MIN_INTERVAL:
        time.sleep(ARXIV_MIN_INTERVAL - elapsed)
    _last_call = time.monotonic()


def _paper_to_dict(paper):
    return {
        "id": paper.entry_id.split("/abs/")[-1],
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "abstract": paper.summary,
        "published": paper.published.strftime("%Y-%m-%d"),
        "categories": paper.categories,
        "pdf_url": paper.pdf_url,
        "arxiv_url": paper.entry_id,
    }


def main():
    parser = argparse.ArgumentParser(description="Search arXiv papers by topic")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--date-from", help="Start date YYYY-MM-DD")
    parser.add_argument("--date-to", help="End date YYYY-MM-DD")
    parser.add_argument("--max-results", type=int, default=50, help="Max results (default 50)")
    parser.add_argument("--sort-by", choices=["relevance", "date"], default="relevance",
                        help="Sort order (default: relevance)")
    args = parser.parse_args()

    # Build query
    q = f"all:{args.query}"
    if args.date_from or args.date_to:
        df = (args.date_from or "1991-01-01").replace("-", "")
        dt = (args.date_to or "2099-12-31").replace("-", "")
        q += f" AND submittedDate:[{df}0000 TO {dt}2359]"

    sort_criterion = (
        arxiv.SortCriterion.SubmittedDate if args.sort_by == "date"
        else arxiv.SortCriterion.Relevance
    )

    _rate_limit()
    client = arxiv.Client(page_size=100, delay_seconds=3.0)
    search = arxiv.Search(
        query=q,
        max_results=args.max_results,
        sort_by=sort_criterion,
    )

    papers = []
    seen_ids = set()
    for result in client.results(search):
        paper = _paper_to_dict(result)
        if paper["id"] not in seen_ids:
            seen_ids.add(paper["id"])
            papers.append(paper)

    output = {"papers": papers, "count": len(papers), "query": args.query}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
