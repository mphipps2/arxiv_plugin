#!/usr/bin/env python3
"""Fetch a single arXiv paper's metadata and optionally extract PDF text.

Usage:
    python fetch_paper.py --id 2603.02926
    python fetch_paper.py --query "speculative decoding reinforcement learning"
    python fetch_paper.py --id 2603.02926 --pdf-text
"""

import argparse
import json
import logging
import sys
import tempfile
from pathlib import Path

import arxiv
import requests

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger("fetch-paper")


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


def extract_pdf_text(pdf_url, max_pages=20):
    """Download PDF and extract text. Returns text or None on failure."""
    try:
        import fitz  # pymupdf
    except ImportError:
        log.warning("pymupdf not installed — skipping PDF text extraction")
        return None

    try:
        log.info("Downloading PDF from %s ...", pdf_url)
        resp = requests.get(pdf_url, timeout=60)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        doc = fitz.open(tmp_path)
        pages = min(len(doc), max_pages)
        text_parts = []
        for i in range(pages):
            text_parts.append(doc[i].get_text())
        doc.close()
        Path(tmp_path).unlink(missing_ok=True)

        text = "\n".join(text_parts).strip()
        log.info("Extracted %d chars from %d pages", len(text), pages)
        return text
    except Exception as exc:
        log.warning("PDF extraction failed: %s", exc)
        return None


def main():
    parser = argparse.ArgumentParser(description="Fetch a single arXiv paper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", help="arXiv paper ID (e.g. 2603.02926)")
    group.add_argument("--query", help="Search query to find a paper")
    parser.add_argument("--pdf-text", action="store_true", help="Extract text from PDF")
    parser.add_argument("--max-results", type=int, default=5, help="Max search results for --query")
    args = parser.parse_args()

    client = arxiv.Client()

    if args.id:
        search = arxiv.Search(id_list=[args.id])
        results = list(client.results(search))
        if not results:
            print(json.dumps({"error": f"Paper {args.id} not found"}))
            sys.exit(1)
        papers = [_paper_to_dict(results[0])]
    else:
        search = arxiv.Search(
            query=args.query,
            max_results=args.max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = list(client.results(search))
        if not results:
            print(json.dumps({"error": f"No papers found for query: {args.query}"}))
            sys.exit(1)
        papers = [_paper_to_dict(r) for r in results]

    output = {"papers": papers, "count": len(papers)}

    if args.pdf_text and papers:
        pdf_text = extract_pdf_text(papers[0]["pdf_url"])
        if pdf_text:
            output["pdf_text"] = pdf_text

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
