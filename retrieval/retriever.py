"""
Retrieval module — KnowSure.

Converts a user query into an embedding and searches ChromaDB
for the most semantically relevant document chunks.

Accepts an optional pre-computed query_embedding so the orchestrator
can reuse the embedding computed during SME cache lookup without
embedding the query twice.
"""

from __future__ import annotations
from typing import Any

from embeddings.embedder import embed_query
from vectorstore.chroma_store import search
from config.settings import TOP_K_RESULTS
from utils.logger import get_logger

logger = get_logger(__name__)


def retrieve(
    query: str,
    top_k: int | None = None,
    collection_name: str | None = None,
    filter_metadata: dict[str, Any] | None = None,
    query_embedding: list[float] | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve the most relevant document chunks for a user query.

    Args:
        query:            User's natural language question.
        top_k:            Number of chunks to retrieve.
        collection_name:  ChromaDB collection to search.
        filter_metadata:  Optional metadata filter.
        query_embedding:  Pre-computed embedding (avoids re-embedding if already done).

    Returns:
        List of retrieved chunk dicts ordered by relevance (best first).
    """
    query = query.strip()
    if not query:
        logger.warning("Empty query received — returning no results.")
        return []

    k = top_k or TOP_K_RESULTS

    logger.info("Retrieving top-%d chunks for query: '%s'", k, query[:80])

    # Use pre-computed embedding if provided, otherwise compute now
    if query_embedding is None:
        query_embedding = embed_query(query)

    results = search(
        query_embedding=query_embedding,
        top_k=k,
        collection_name=collection_name,
        filter_metadata=filter_metadata,
    )

    logger.info("Retrieved %d chunk(s).", len(results))

    if not results:
        logger.warning("No relevant chunks found for query: '%s'", query)

    return results


def format_context(chunks: list[dict[str, Any]]) -> str:
    """
    Format retrieved chunks into a context string for the LLM prompt.

    Args:
        chunks: List of chunk dicts from retrieve().

    Returns:
        Formatted context string ready for LLM prompt injection.
    """
    if not chunks:
        return "No relevant context was found in the knowledge base."

    context_parts = []

    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "Unknown")
        page   = chunk.get("page", "N/A")
        text   = chunk.get("text", "").strip()
        header = f"[Source {i}: {source} | Page {page}]"
        context_parts.append(f"{header}\n{text}")

    return "\n\n---\n\n".join(context_parts)