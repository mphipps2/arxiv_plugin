#!/usr/bin/env python3
"""Fetch arXiv papers day-by-day and cache as JSON files.

Usage:
    python fetch_papers.py --config config.yaml --start-date 2026-03-01 --end-date 2026-03-07
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import arxiv
import yaml

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger("fetch-papers")

ARXIV_MIN_INTERVAL = 3.0
_last_arxiv_call = 0.0


def _rate_limit():
    global _last_arxiv_call
    now = time.monotonic()
    elapsed = now - _last_arxiv_call
    if elapsed < ARXIV_MIN_INTERVAL:
        time.sleep(ARXIV_MIN_INTERVAL - elapsed)
    _last_arxiv_call = time.monotonic()


def _paper_to_dict(paper):
    return {
        "id": paper.entry_id.split("/abs/")[-1],
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "abstract": paper.summary,
        "published": paper.published.strftime("%Y-%m-%d"),
        "updated": paper.updated.strftime("%Y-%m-%d") if paper.updated else None,
        "categories": paper.categories,
        "pdf_url": paper.pdf_url,
        "arxiv_url": paper.entry_id,
        "comment": paper.comment,
        "journal_ref": paper.journal_ref,
    }


def fetch_day(date_str, categories, max_results=200):
    """Fetch all papers for a single day from arXiv."""
    cat_expr = " OR ".join(f"cat:{c}" for c in categories)
    d = date_str.replace("-", "")
    query = f"({cat_expr}) AND submittedDate:[{d}0000 TO {d}2359]"

    _rate_limit()
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )

    papers = []
    seen_ids = set()
    for result in client.results(search):
        paper = _paper_to_dict(result)
        if paper["id"] not in seen_ids:
            seen_ids.add(paper["id"])
            papers.append(paper)

    return {
        "date": date_str,
        "categories": categories,
        "count": len(papers),
        "papers": papers,
    }


def should_fetch(date_str, cache_dir, today_str):
    """Decide whether to fetch papers for a given date."""
    cache_file = cache_dir / f"{date_str}.json"

    # Today: always re-fetch
    if date_str == today_str:
        return True

    # If cache exists for this date...
    if cache_file.exists():
        # Yesterday: re-fetch only if today's cache doesn't exist yet
        yesterday = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        if date_str == yesterday:
            today_cache = cache_dir / f"{today_str}.json"
            if not today_cache.exists():
                return True  # First run today, yesterday may be incomplete
        return False  # Cached and not stale

    return True  # No cache file


def main():
    parser = argparse.ArgumentParser(description="Fetch arXiv papers day-by-day")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    categories = config.get("categories", ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML"])
    output_dir = Path(config.get("output_dir", "./arxiv-output"))
    cache_dir = output_dir / "cache" / "papers"
    cache_dir.mkdir(parents=True, exist_ok=True)

    start = datetime.strptime(args.start_date, "%Y-%m-%d")
    end = datetime.strptime(args.end_date, "%Y-%m-%d")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total_fetched = 0
    total_cached = 0
    current = start

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        cache_file = cache_dir / f"{date_str}.json"

        if should_fetch(date_str, cache_dir, today_str):
            log.info("Fetching %s ...", date_str)
            data = fetch_day(date_str, categories)
            cache_file.write_text(json.dumps(data, indent=2))
            log.info("  -> %d papers", data["count"])
            total_fetched += 1
        else:
            existing = json.loads(cache_file.read_text())
            log.info("Cached  %s (%d papers)", date_str, existing["count"])
            total_cached += 1

        current += timedelta(days=1)

    log.info("Done: %d days fetched, %d days cached", total_fetched, total_cached)


if __name__ == "__main__":
    main()
