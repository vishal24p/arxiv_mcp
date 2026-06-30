"""arXiv API client.

Two jobs:
  - search():   hit arXiv's public API, return metadata
  - download(): fetch a PDF and save it to papers/

No PDF parsing. No LLM. No vector store. Just HTTP.
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_PDF = "https://arxiv.org/pdf/"

# Where downloaded PDFs land. Override with ARXIV_MCP_PAPERS_DIR env var.
_DEFAULT_PAPERS_DIR = Path(__file__).resolve().parent.parent.parent / "papers"


def _papers_dir() -> Path:
    import os
    override = os.environ.get("ARXIV_MCP_PAPERS_DIR")
    return Path(override).expanduser() if override else _DEFAULT_PAPERS_DIR


# Atom namespace. arXiv's API returns Atom feeds; we have to declare it
# to ElementTree so findtext/findall know where to look.
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


@dataclass(frozen=True)
class Paper:
    arxiv_id: str   # "1706.03762" — version stripped
    title: str
    authors: list[str]
    abstract: str
    published: str  # ISO 8601 string from arXiv
    pdf_url: str    # full URL to the PDF

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "published": self.published,
            "pdf_url": self.pdf_url,
        }


def _strip_version(arxiv_id: str) -> str:
    """1706.03762v7 -> 1706.03762. arXiv canonicalizes via the bare id."""
    return re.sub(r"v\d+$", "", arxiv_id)


# ---------- search ----------

def search(query: str, max_results: int = 10) -> list[Paper]:
    """Free-text search on arXiv. all:\"phrase\" matches the whole record."""
    params = {
        "search_query": f'all:"{query}"',
        "max_results": str(max_results),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    resp = httpx.get(ARXIV_API, params=params, timeout=30.0)
    resp.raise_for_status()
    return _parse_entries(resp.text)


def _parse_entries(xml_text: str) -> list[Paper]:
    root = ET.fromstring(xml_text)
    papers: list[Paper] = []
    for entry in root.findall("a:entry", ATOM_NS):
        raw_id = entry.findtext("a:id", namespaces=ATOM_NS, default="")
        arxiv_id = _strip_version(raw_id.rsplit("/", 1)[-1])
        if not arxiv_id:
            continue
        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=" ".join(
                    entry.findtext("a:title", namespaces=ATOM_NS, default="").split()
                ),
                authors=[
                    a.findtext("a:name", namespaces=ATOM_NS, default="")
                    for a in entry.findall("a:author", ATOM_NS)
                ],
                abstract=" ".join(
                    entry.findtext("a:summary", namespaces=ATOM_NS, default="").split()
                ),
                published=entry.findtext("a:published", namespaces=ATOM_NS, default=""),
                pdf_url=f"{ARXIV_PDF}{arxiv_id}",
            )
        )
    return papers


# ---------- download ----------

def download(arxiv_id: str) -> Path:
    """Stream a PDF into papers/<id>.pdf. Idempotent."""
    arxiv_id = _strip_version(arxiv_id)
    dest_dir = _papers_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{arxiv_id}.pdf"
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    url = f"{ARXIV_PDF}{arxiv_id}"
    with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=64 * 1024):
                f.write(chunk)
    return dest
