#!/usr/bin/env python3
"""Search OpenAlex for institutional activity on a research topic.

Usage:
    python search_institutions.py --query "large language models" \
        --institutions "OpenAI" "Google DeepMind" "Meta AI" \
        --date-from 2026-02-01 --date-to 2026-03-01
"""

import argparse
import json
import logging
import sys
import time

import requests

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger("search-institutions")

OPENALEX_API = "https://api.openalex.org"


def _rate_limit():
    time.sleep(0.15)  # polite pacing for OpenAlex


def resolve_institution(name):
    """Resolve institution name to OpenAlex ID."""
    _rate_limit()
    url = f"{OPENALEX_API}/autocomplete/institutions"
    try:
        resp = requests.get(url, params={"q": name}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return {"id": results[0]["id"], "display_name": results[0].get("display_name", name)}
    except Exception as exc:
        log.warning("Failed to resolve institution '%s': %s", name, exc)
    return None


def fetch_institution_papers(openalex_id, date_from=None, date_to=None, topic_query=None):
    """Fetch papers from an institution within a date range."""
    _rate_limit()
    filters = [f"institutions.id:{openalex_id}"]
    if date_from:
        filters.append(f"from_publication_date:{date_from}")
    if date_to:
        filters.append(f"to_publication_date:{date_to}")

    params = {
        "filter": ",".join(filters),
        "per_page": 50,
        "select": "id,title,authorships,publication_date,ids",
    }
    if topic_query:
        params["search"] = topic_query

    try:
        resp = requests.get(f"{OPENALEX_API}/works", params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", []), data.get("meta", {}).get("count", 0)
    except Exception as exc:
        log.warning("Failed to fetch papers: %s", exc)
        return [], 0


def main():
    parser = argparse.ArgumentParser(description="Search OpenAlex for institutional activity")
    parser.add_argument("--query", help="Research topic to filter by")
    parser.add_argument("--institutions", nargs="+", required=True, help="Institution names to check")
    parser.add_argument("--date-from", help="Start date YYYY-MM-DD")
    parser.add_argument("--date-to", help="End date YYYY-MM-DD")
    args = parser.parse_args()

    results = []
    for name in args.institutions:
        log.info("Resolving %s ...", name)
        resolved = resolve_institution(name)
        if not resolved:
            log.warning("Could not resolve: %s", name)
            continue

        papers, total_count = fetch_institution_papers(
            resolved["id"],
            date_from=args.date_from,
            date_to=args.date_to,
            topic_query=args.query,
        )

        # Extract paper titles for focus area analysis
        paper_titles = [p.get("title", "") for p in papers if p.get("title")]

        if total_count > 0:
            activity = "high" if total_count >= 5 else ("medium" if total_count >= 2 else "low")
            results.append({
                "name": resolved["display_name"],
                "papers": total_count,
                "activity_level": activity,
                "sample_titles": paper_titles[:10],
            })

    results.sort(key=lambda r: r["papers"], reverse=True)

    output = {"institutions": results, "count": len(results)}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
