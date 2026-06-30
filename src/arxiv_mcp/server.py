"""MCP server: search + download arXiv papers."""
from mcp.server.fastmcp import FastMCP

from .arxiv_client import download, search

mcp = FastMCP("arxiv-mcp")


@mcp.tool()
def search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    """Search arXiv for papers by free-text query.

    Returns metadata only (title, authors, abstract, pdf_url, published
    date). Does not download or parse PDFs. Call download_paper with
    one of the returned arxiv_id values to fetch a PDF locally.

    Args:
        query: Search terms, e.g. "attention is all you need".
        max_results: Cap on results (default 10).
    """
    return [p.to_dict() for p in search(query, max_results=max_results)]


@mcp.tool()
def download_paper(arxiv_id: str) -> dict:
    """Download a paper's PDF from arXiv into the local papers/ directory.

    Idempotent: if the file already exists locally, returns the existing
    path without re-downloading.

    Args:
        arxiv_id: The arXiv identifier, e.g. "1706.03762". A version
                  suffix like "v7" is also accepted and ignored.
    """
    path = download(arxiv_id)
    return {
        "arxiv_id": path.stem,
        "path": str(path),
        "size_bytes": path.stat().st_size,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
