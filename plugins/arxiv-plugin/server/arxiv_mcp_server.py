#!/usr/bin/env python3
"""ArXiv MCP server — exposes search, paper lookup, daily papers, and institution enrichment tools."""

import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import arxiv
import requests
import yaml
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging (stderr only — stdout is reserved for MCP protocol)
# ---------------------------------------------------------------------------
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("arxiv-mcp")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
_config_path = os.path.join(_plugin_root, "config.yaml")

try:
    with open(_config_path) as f:
        CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    CONFIG = {}
    log.warning("config.yaml not found at %s — using defaults", _config_path)

DEFAULT_CATEGORIES: list[str] = CONFIG.get("categories", ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML"])
DEFAULT_INSTITUTIONS: list[str] = CONFIG.get("institutions", [])
OUTPUT_DIR: str = CONFIG.get("output_dir", "./arxiv-output")
OPENALEX_EMAIL: str | None = CONFIG.get("openalex_email")

# ---------------------------------------------------------------------------
# Rate limiter (arXiv asks for ≥3 s between requests)
# ---------------------------------------------------------------------------
_last_arxiv_call: float = 0.0
ARXIV_MIN_INTERVAL = 3.0


def _rate_limit() -> None:
    global _last_arxiv_call
    now = time.monotonic()
    elapsed = now - _last_arxiv_call
    if elapsed < ARXIV_MIN_INTERVAL:
        time.sleep(ARXIV_MIN_INTERVAL - elapsed)
    _last_arxiv_call = time.monotonic()


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}  # key -> {"value": ..., "ts": float}

TTLS: dict[str, int] = {
    "get_daily_papers": 86400,      # 24 h
    "get_paper": 21600,             # 6 h
    "enrich_institutions": 43200,   # 12 h
    "search_papers": 3600,          # 1 h
    "search_by_institution": 3600,  # 1 h
}


def _cache_key(tool: str, params: dict) -> str:
    raw = tool + json.dumps(params, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(tool: str, params: dict):
    key = _cache_key(tool, params)
    entry = _cache.get(key)
    if entry is None:
        return None
    ttl = TTLS.get(tool, 3600)
    if time.time() - entry["ts"] > ttl:
        del _cache[key]
        return None
    log.info("cache hit for %s", tool)
    return entry["value"]


def _cache_set(tool: str, params: dict, value):
    key = _cache_key(tool, params)
    _cache[key] = {"value": value, "ts": time.time()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _paper_to_dict(paper: arxiv.Result) -> dict:
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


def _openalex_headers() -> dict:
    headers = {"Accept": "application/json"}
    if OPENALEX_EMAIL:
        headers["mailto"] = OPENALEX_EMAIL
        headers["User-Agent"] = f"arxiv-plugin/0.1.0 (mailto:{OPENALEX_EMAIL})"
    return headers


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("arxiv")


@mcp.tool()
def search_papers(
    query: str,
    categories: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    max_results: int = 50,
    sort_by: str = "relevance",
) -> dict:
    """Search arXiv for papers matching a query.

    Args:
        query: Search query string.
        categories: Optional list of arXiv categories to filter (e.g. ["cs.AI", "cs.LG"]).
        date_from: Optional start date YYYY-MM-DD.
        date_to: Optional end date YYYY-MM-DD.
        max_results: Maximum papers to return (default 50).
        sort_by: Sort order — "relevance" or "submittedDate".
    """
    params = {
        "query": query, "categories": categories,
        "date_from": date_from, "date_to": date_to,
        "max_results": max_results, "sort_by": sort_by,
    }
    cached = _cache_get("search_papers", params)
    if cached is not None:
        return cached

    # Build query string
    parts = [f"all:{query}"]
    cats = categories or []
    if cats:
        cat_expr = " OR ".join(f"cat:{c}" for c in cats)
        parts.append(f"({cat_expr})")
    q = " AND ".join(parts)

    # Date range
    if date_from or date_to:
        df = (date_from or "1991-01-01").replace("-", "")
        dt = (date_to or "2099-12-31").replace("-", "")
        q += f" AND submittedDate:[{df}0000 TO {dt}2359]"

    sort_criterion = (
        arxiv.SortCriterion.SubmittedDate if sort_by == "submittedDate"
        else arxiv.SortCriterion.Relevance
    )

    _rate_limit()
    client = arxiv.Client()
    search = arxiv.Search(query=q, max_results=max_results, sort_by=sort_criterion)

    papers = [_paper_to_dict(r) for r in client.results(search)]
    result = {"papers": papers, "count": len(papers)}
    _cache_set("search_papers", params, result)
    return result


@mcp.tool()
def get_paper(arxiv_id: str) -> dict:
    """Get detailed metadata for a single arXiv paper.

    Args:
        arxiv_id: The arXiv paper ID (e.g. "2301.07041" or "2301.07041v1").
    """
    params = {"arxiv_id": arxiv_id}
    cached = _cache_get("get_paper", params)
    if cached is not None:
        return cached

    _rate_limit()
    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    results = list(client.results(search))
    if not results:
        return {"error": f"Paper {arxiv_id} not found"}

    result = _paper_to_dict(results[0])
    _cache_set("get_paper", params, result)
    return result


@mcp.tool()
def get_daily_papers(
    date: str | None = None,
    categories: list[str] | None = None,
) -> dict:
    """Get papers submitted on a specific date.

    Args:
        date: Date in YYYY-MM-DD format (defaults to yesterday UTC).
        categories: Optional list of arXiv categories to filter.
    """
    if date is None:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%d")

    cats = categories or DEFAULT_CATEGORIES

    params = {"date": date, "categories": cats}
    cached = _cache_get("get_daily_papers", params)
    if cached is not None:
        return cached

    result = search_papers(
        query="*",
        categories=cats,
        date_from=date,
        date_to=date,
        max_results=200,
        sort_by="submittedDate",
    )

    output = {
        "date": date,
        "papers": result["papers"],
        "categories": cats,
        "count": result["count"],
    }
    _cache_set("get_daily_papers", params, output)
    return output


@mcp.tool()
def enrich_institutions(arxiv_ids: list[str]) -> dict:
    """Look up institutional affiliations for papers via OpenAlex.

    Args:
        arxiv_ids: List of arXiv IDs to enrich with institution data.
    """
    params = {"arxiv_ids": sorted(arxiv_ids)}
    cached = _cache_get("enrich_institutions", params)
    if cached is not None:
        return cached

    headers = _openalex_headers()
    papers = []

    for aid in arxiv_ids:
        # Normalize ID — strip version suffix for OpenAlex lookup
        clean_id = aid.split("v")[0] if "v" in aid else aid
        url = f"https://api.openalex.org/works?filter=ids.arxiv:{clean_id}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.warning("OpenAlex lookup failed for %s: %s", aid, exc)
            papers.append({"arxiv_id": aid, "institutions": []})
            continue

        institutions = []
        seen = set()
        for work in data.get("results", []):
            for authorship in work.get("authorships", []):
                for inst in authorship.get("institutions", []):
                    name = inst.get("display_name", "")
                    if name and name not in seen:
                        seen.add(name)
                        institutions.append({
                            "name": name,
                            "country": inst.get("country_code", ""),
                            "type": inst.get("type", ""),
                        })

        papers.append({"arxiv_id": aid, "institutions": institutions})
        time.sleep(0.1)  # polite pacing for OpenAlex

    result = {"papers": papers}
    _cache_set("enrich_institutions", params, result)
    return result


@mcp.tool()
def search_by_institution(
    institution: str,
    date_from: str | None = None,
    date_to: str | None = None,
    categories: list[str] | None = None,
) -> dict:
    """Search for arXiv papers from a specific institution via OpenAlex.

    Args:
        institution: Institution name (e.g. "OpenAI", "MIT").
        date_from: Optional start date YYYY-MM-DD.
        date_to: Optional end date YYYY-MM-DD.
        categories: Optional arXiv categories to filter results.
    """
    params = {
        "institution": institution, "date_from": date_from,
        "date_to": date_to, "categories": categories,
    }
    cached = _cache_get("search_by_institution", params)
    if cached is not None:
        return cached

    headers = _openalex_headers()

    # Step 1: resolve institution via autocomplete
    auto_url = f"https://api.openalex.org/autocomplete/institutions?q={institution}"
    try:
        auto_resp = requests.get(auto_url, headers=headers, timeout=10)
        auto_resp.raise_for_status()
        suggestions = auto_resp.json().get("results", [])
    except Exception as exc:
        return {"error": f"Institution lookup failed: {exc}"}

    if not suggestions:
        return {"error": f"Institution '{institution}' not found in OpenAlex"}

    inst_id = suggestions[0]["id"]  # e.g. https://openalex.org/I123456
    inst_display = suggestions[0].get("display_name", institution)

    # Step 2: query works
    filters = [f"institutions.id:{inst_id}"]
    if date_from:
        filters.append(f"from_publication_date:{date_from}")
    if date_to:
        filters.append(f"to_publication_date:{date_to}")
    filter_str = ",".join(filters)

    works_url = f"https://api.openalex.org/works?filter={filter_str}&per_page=100"
    try:
        works_resp = requests.get(works_url, headers=headers, timeout=20)
        works_resp.raise_for_status()
        works_data = works_resp.json()
    except Exception as exc:
        return {"error": f"Works query failed: {exc}"}

    # Filter to papers that have arXiv IDs
    papers = []
    for work in works_data.get("results", []):
        arxiv_id = None
        for loc in work.get("locations", []):
            landing = loc.get("landing_page_url", "") or ""
            if "arxiv.org" in landing:
                arxiv_id = landing.split("/abs/")[-1] if "/abs/" in landing else None
                break

        if not arxiv_id:
            ids_obj = work.get("ids", {})
            if ids_obj.get("arxiv"):
                arxiv_id = ids_obj["arxiv"].replace("https://arxiv.org/abs/", "")

        if not arxiv_id:
            continue

        paper_cats = []
        for concept in work.get("concepts", []):
            paper_cats.append(concept.get("display_name", ""))

        papers.append({
            "id": arxiv_id,
            "title": work.get("title", ""),
            "authors": [a.get("author", {}).get("display_name", "") for a in work.get("authorships", [])],
            "published": work.get("publication_date", ""),
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "categories": paper_cats,
        })

    result = {
        "institution": inst_display,
        "openalex_id": inst_id,
        "papers": papers,
        "count": len(papers),
    }
    _cache_set("search_by_institution", params, result)
    return result


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
