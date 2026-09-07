"""PDF parser using PyMuPDF — extracts text page-by-page with layout awareness.

Returns a list of PageChunk objects for downstream fact extraction.
Logs pages with no extractable text as extraction issues.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf  # PyMuPDF


@dataclass
class PageChunk:
    """One page of extracted text from a PDF."""

    page_number: int  # 1-indexed
    text: str
    char_count: int
    has_images: bool = False
    has_tables: bool = False


@dataclass
class ParseResult:
    """Result of parsing a single PDF."""

    file_path: str
    filename: str
    sha256: str
    page_count: int
    pages: list[PageChunk] = field(default_factory=list)
    empty_pages: list[int] = field(default_factory=list)  # pages with no text


def compute_sha256(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file for deduplication."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pdf(file_path: str | Path) -> ParseResult:
    """Parse a PDF file and extract text page-by-page.

    Args:
        file_path: Path to the PDF file.

    Returns:
        ParseResult with page-level text chunks and metadata.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        pymupdf.FileDataError: If the file isn't a valid PDF.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    sha256 = compute_sha256(file_path)

    doc = pymupdf.open(str(file_path))
    page_count = len(doc)
    pages: list[PageChunk] = []
    empty_pages: list[int] = []

    for page_idx in range(page_count):
        page = doc[page_idx]
        page_number = page_idx + 1  # 1-indexed

        # Extract text with layout preservation
        # "text" mode gives plain text; "blocks" gives structured blocks
        text = page.get_text("text")

        # Clean up: normalize whitespace but preserve meaningful line breaks
        text = text.strip()

        # Check for images on the page
        has_images = len(page.get_images(full=True)) > 0

        # Check for tables (heuristic: look for tab-separated or grid-like content)
        has_tables = "\t" in text or _looks_like_table(text)

        char_count = len(text)

        if char_count == 0:
            # Page has no extractable text — might be scanned/image-only
            empty_pages.append(page_number)
        else:
            pages.append(
                PageChunk(
                    page_number=page_number,
                    text=text,
                    char_count=char_count,
                    has_images=has_images,
                    has_tables=has_tables,
                )
            )

    doc.close()

    return ParseResult(
        file_path=str(file_path),
        filename=file_path.name,
        sha256=sha256,
        page_count=page_count,
        pages=pages,
        empty_pages=empty_pages,
    )


def _looks_like_table(text: str) -> bool:
    """Simple heuristic to detect table-like content."""
    lines = text.split("\n")
    if len(lines) < 3:
        return False

    # Count lines with multiple number-like tokens separated by spaces
    numeric_lines = 0
    for line in lines:
        tokens = line.split()
        if len(tokens) >= 3:
            numeric_count = sum(
                1 for t in tokens if _is_numeric_token(t)
            )
            if numeric_count >= 2:
                numeric_lines += 1

    return numeric_lines >= 3


def _is_numeric_token(token: str) -> bool:
    """Check if a token looks numeric (handles commas, percentages, currency)."""
    cleaned = token.replace(",", "").replace("%", "").replace("₹", "").replace("$", "")
    cleaned = cleaned.replace("(", "").replace(")", "").replace("-", "")
    try:
        float(cleaned)
        return True
    except ValueError:
        return False
