#!/usr/bin/env python3
"""Download WSDC rules PDFs and cache extracted text for tier-chart provenance.

Usage:
    python scripts/extract_rules_charts.py
    python scripts/extract_rules_charts.py --skip-download

Requires pypdf (see requirements-dev.txt). Cached text lands in
data/reference/rules_text/; PDFs in data/reference/rules_pdfs/ (gitignored).
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = PROJECT_ROOT / "data" / "reference" / "rules_pdfs"
TEXT_DIR = PROJECT_ROOT / "data" / "reference" / "rules_text"
BASE_URL = "https://wsdc-analytics.github.io/static/rules"

RULE_PDFS: tuple[str, ...] = (
    "WSDC-Points-Registry-2002.pdf",
    "WSDC-Points-Registry-2004.pdf",
    "WSDC%20Points%20Registry%20Document_2007.pdf",
    "WSDC%20Points%20Registry%20Document_2009.pdf",
    "WSDC%20Points%20Registry%20Document_2011.pdf",
    "2015-WSDC-Registry-Event-Rules-Combined.pdf",
    "2018-WSDC-Registry-Event-Rules-Combined.pdf",
    "2019-WSDC-Registry-Event-Rules-Combined.pdf",
    "2020-WSDC-Registry-Event-Rules-Combined.pdf",
    "2020-May-Addendum.pdf",
    "2023-Registry-Event-Rules_vFinal2-2023.1B.pdf",
    "2023-Registry-Event-Rules_vFinal3b-2023.1D.pdf",
    "2024-Registry-Event-Rules_vFRER-Version-2024.1A.pdf",
    "2024-Registry-Event-Rules_v2024.1B.pdf",
    "2024-Registry-Event-Rules_v2024.2A.pdf",
    "2024-Registry-Event-Rules_v2024.2B.pdf",
    "wsdcrules.pdf",
    "WSDC-Registry-Event-Rules-Jan-17-2026.pdf",
)

KEYWORDS = re.compile(
    r"tier|points awarded|chart\s*[456]|competitors?|preliminar|entries",
    re.I,
)


def _local_name(url_name: str) -> str:
    return urllib.parse.unquote(url_name)


def download_pdfs() -> list[Path]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for url_name in RULE_PDFS:
        local = PDF_DIR / _local_name(url_name)
        if not local.exists():
            url = f"{BASE_URL}/{url_name}"
            print(f"GET {url}")
            urllib.request.urlretrieve(url, local)
        paths.append(local)
    return paths


def extract_text(pdf_path: Path) -> tuple[str, list[int]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "pypdf is required. Install with: pip install -r requirements-dev.txt"
        ) from exc

    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    hits: list[int] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"===== PAGE {i} =====\n{text}")
        if KEYWORDS.search(text):
            hits.append(i)
    return "\n\n".join(pages), hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Only re-extract text from already-downloaded PDFs",
    )
    args = parser.parse_args()

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = list(PDF_DIR.glob("*.pdf")) if args.skip_download else download_pdfs()
    if not pdfs:
        print("No PDFs found", file=sys.stderr)
        return 1

    for pdf in sorted(pdfs):
        text, hits = extract_text(pdf)
        out = TEXT_DIR / f"{pdf.stem}.txt"
        out.write_text(text, encoding="utf-8")
        print(f"{pdf.name}: chars={len(text.strip())} hit_pages={hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
