"""
Document chunking module.

Splits extracted text sections into smaller overlapping chunks
suitable for embedding and retrieval.

Design decisions:
  - Character-based splitting with configurable chunk_size and overlap
  - Overlap prevents context loss at chunk boundaries
  - Each chunk inherits metadata from its parent section
  - Chunks shorter than MIN_CHUNK_LENGTH are discarded (likely noise)
  - chunk_index is tracked per-document for ordered citation

Why character-based (not token-based)?
  For a sentence-transformers model like all-MiniLM-L6-v2, the practical
  input limit is ~256 tokens (~1000 characters). Character-based chunking
  is simpler and predictable without requiring a tokenizer dependency.
  When upgrading to an LLM-native embedding model, switch to token-based.
"""

from typing import Any

from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_LENGTH
from utils.logger import get_logger

logger = get_logger(__name__)


def chunk_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert a list of page/section dicts into overlapping text chunks.

    Args:
        pages: Output from the ingestion pipeline — list of dicts with
               'text', 'source', 'page', and 'doc_type' keys.

    Returns:
        List of chunk dicts with:
            - text        : chunk text content
            - source      : originating document filename
            - page        : page/section number from source document
            - doc_type    : document format type
            - chunk_index : sequential index within the document
    """
    all_chunks: list[dict[str, Any]] = []
    # Track chunk index per source document independently
    doc_chunk_counters: dict[str, int] = {}

    for page in pages:
        source = page.get("source", "unknown")
        text = page.get("text", "").strip()

        if not text:
            continue

        raw_chunks = _split_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

        for raw_chunk in raw_chunks:
            if len(raw_chunk.strip()) < MIN_CHUNK_LENGTH:
                continue  # discard near-empty chunks

            # Increment chunk counter for this document
            doc_chunk_counters[source] = doc_chunk_counters.get(source, 0) + 1

            chunk = {
                "text":        raw_chunk.strip(),
                "source":      source,
                "page":        page.get("page", 1),
                "doc_type":    page.get("doc_type", "unknown"),
                "chunk_index": doc_chunk_counters[source],
            }

            # Preserve optional section metadata if present (e.g. from xlsx)
            if "section" in page:
                chunk["section"] = page["section"]

            all_chunks.append(chunk)

    logger.info(
        "Produced %d chunks from %d page/section(s)", len(all_chunks), len(pages)
    )
    return all_chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping fixed-size character chunks.

    Args:
        text:       Full text to split.
        chunk_size: Maximum characters per chunk.
        overlap:    Number of characters to repeat between consecutive chunks.

    Returns:
        List of text chunk strings.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary (". ") within the last 100 chars
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary != -1 and boundary > start + (chunk_size // 2):
                end = boundary + 1  # include the period

        chunk = text[start:end]
        chunks.append(chunk)

        # Advance start by chunk_size minus overlap
        start += chunk_size - overlap

        # Prevent infinite loop if chunk_size <= overlap (misconfiguration)
        if chunk_size <= overlap:
            logger.error(
                "CHUNK_SIZE (%d) must be greater than CHUNK_OVERLAP (%d). "
                "Aborting split.", chunk_size, overlap
            )
            break

    return chunks