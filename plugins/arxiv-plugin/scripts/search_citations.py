#!/usr/bin/env python3
"""Search Semantic Scholar for papers with actual citation counts.

Usage:
    python search_citations.py --query "attention mechanisms" --limit 20
    python search_citations.py --arxiv-ids 1706.03762 2005.14165 1810.04805
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
log = logging.getLogger("search-citations")

S2_API = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "title,authors,citationCount,influentialCitationCount,year,externalIds,abstract,url"
S2_RATE_LIMIT = 1.0  # 1 request/second for unauthenticated
_last_call = 0.0


def _rate_limit():
    global _last_call
    now = time.monotonic()
    elapsed = now - _last_call
    if elapsed < S2_RATE_LIMIT:
        time.sleep(S2_RATE_LIMIT - elapsed)
    _last_call = time.monotonic()


def _normalize_paper(paper):
    """Normalize Semantic Scholar paper to a consistent format."""
    ext_ids = paper.get("externalIds") or {}
    arxiv_id = ext_ids.get("ArXiv")
    return {
        "id": arxiv_id or paper.get("paperId", ""),
        "title": paper.get("title", ""),
        "authors": [a.get("name", "") for a in (paper.get("authors") or [])],
        "year": paper.get("year"),
        "citation_count": paper.get("citationCount", 0),
        "influential_citation_count": paper.get("influentialCitationCount", 0),
        "abstract": paper.get("abstract", ""),
        "url": paper.get("url", ""),
        "arxiv_id": arxiv_id,
    }


def search_by_topic(query, limit=20):
    """Search Semantic Scholar for papers, sorted by citation count."""
    _rate_limit()
    url = f"{S2_API}/paper/search"
    params = {
        "query": query,
        "fields": S2_FIELDS,
        "limit": min(limit, 100),
        "sort": "citationCount:desc",
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.error("Semantic Scholar search failed: %s", exc)
        return []

    return [_normalize_paper(p) for p in data.get("data", [])]


def lookup_by_arxiv_ids(arxiv_ids):
    """Look up citation counts for specific arXiv papers."""
    papers = []
    for aid in arxiv_ids:
        _rate_limit()
        url = f"{S2_API}/paper/ArXiv:{aid}"
        params = {"fields": S2_FIELDS}

        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 404:
                log.warning("Paper ArXiv:%s not found on Semantic Scholar", aid)
                continue
            resp.raise_for_status()
            papers.append(_normalize_paper(resp.json()))
        except Exception as exc:
            log.warning("Lookup failed for ArXiv:%s: %s", aid, exc)

    return papers


def main():
    parser = argparse.ArgumentParser(description="Search Semantic Scholar for citation data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", help="Topic search query")
    group.add_argument("--arxiv-ids", nargs="+", help="arXiv IDs to look up")
    parser.add_argument("--limit", type=int, default=20, help="Max results for topic search (default 20)")
    args = parser.parse_args()

    if args.query:
        papers = search_by_topic(args.query, args.limit)
    else:
        papers = lookup_by_arxiv_ids(args.arxiv_ids)

    # Sort by citation count descending
    papers.sort(key=lambda p: p.get("citation_count", 0), reverse=True)

    output = {"papers": papers, "count": len(papers)}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
