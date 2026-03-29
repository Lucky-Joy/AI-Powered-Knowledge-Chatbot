"""
ChromaDB vector store integration layer.

Responsibilities:
  - Initialize the persistent ChromaDB client
  - Create or retrieve named collections
  - Store chunk embeddings and metadata
  - Execute semantic similarity searches

Architecture notes:
  - Uses PersistentClient so the index survives process restarts
  - Embeddings are provided externally (from embedder.py) — ChromaDB's
    built-in embedding function is NOT used. This keeps the embedding
    model decoupled from the vector store.
  - Each chunk is stored with a deterministic ID based on source + chunk_index
    to support idempotent re-ingestion (re-running won't duplicate chunks)
  - Metadata keys must be primitive types (str, int, float, bool) for Chroma

ChromaDB internals relevant here:
  - HNSW index: approximate nearest-neighbor search, fast at scale
  - Cosine similarity: appropriate for normalized sentence-transformer vectors
  - Persistent storage: written to CHROMA_PERSIST_DIR on disk
"""

import hashlib
from typing import Any

import chromadb
from chromadb.config import Settings

from config.settings import CHROMA_PERSIST_DIR, ACTIVE_COLLECTION, TOP_K_RESULTS
from utils.logger import get_logger

logger = get_logger(__name__)

# Module-level ChromaDB client singleton
_client = None  # type: chromadb.PersistentClient

def _get_client() -> chromadb.PersistentClient:
    """Lazy-initialize the persistent ChromaDB client."""
    global _client
    if _client is None:
        logger.info("Initializing ChromaDB client at: %s", CHROMA_PERSIST_DIR)
        _client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
        )
        logger.info("ChromaDB client initialized.")
    return _client


def get_collection(collection_name: str | None = None) -> chromadb.Collection:
    """
    Retrieve an existing collection or create it if it doesn't exist.

    Args:
        collection_name: Name of the collection. Defaults to ACTIVE_COLLECTION.

    Returns:
        ChromaDB Collection object.
    """
    name = collection_name or ACTIVE_COLLECTION
    client = _get_client()

    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},  # cosine similarity for embeddings
    )
    logger.info("Using ChromaDB collection: '%s'", name)
    return collection


def store_chunks(
    chunks: list[dict[str, Any]],
    collection_name: str | None = None,
) -> None:
    """
    Store embedded chunks into ChromaDB.

    Each chunk must have: text, embedding, source, page, chunk_index, doc_type.

    Args:
        chunks:          List of chunk dicts with embeddings attached.
        collection_name: Target collection (defaults to ACTIVE_COLLECTION).
    """
    if not chunks:
        logger.warning("No chunks provided to store.")
        return

    collection = get_collection(collection_name)

    ids         = []
    embeddings  = []
    documents   = []
    metadatas   = []

    for chunk in chunks:
        # Deterministic ID prevents duplicate storage on re-ingestion
        chunk_id = _make_chunk_id(chunk["source"], chunk["chunk_index"])

        ids.append(chunk_id)
        embeddings.append(chunk["embedding"])
        documents.append(chunk["text"])
        metadatas.append(_build_metadata(chunk))

    # Upsert in batches to respect ChromaDB's max batch size of 5461
    BATCH_SIZE = 5000
    total = len(ids)

    for i in range(0, total, BATCH_SIZE):
        batch_ids        = ids[i:i + BATCH_SIZE]
        batch_embeddings = embeddings[i:i + BATCH_SIZE]
        batch_documents  = documents[i:i + BATCH_SIZE]
        batch_metadatas  = metadatas[i:i + BATCH_SIZE]

        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            documents=batch_documents,
            metadatas=batch_metadatas,
        )
        logger.info(
            "Stored batch %d/%d (%d chunks)...",
            min(i + BATCH_SIZE, total), total, len(batch_ids)
        )

    logger.info(
        "Stored/updated %d chunk(s) in collection '%s'.",
        total, collection.name
    )


def search(
    query_embedding: list[float],
    top_k: int | None = None,
    collection_name: str | None = None,
    filter_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Search the vector store for chunks semantically similar to a query.

    Args:
        query_embedding:  Embedding vector for the user query.
        top_k:            Number of results to return.
        collection_name:  Collection to search (defaults to ACTIVE_COLLECTION).
        filter_metadata:  Optional Chroma `where` clause for metadata filtering.
                          Example: {"doc_type": "pdf"}

    Returns:
        List of result dicts, each containing:
            - text        : chunk text
            - source      : source document
            - page        : page number
            - chunk_index : chunk index
            - score       : cosine distance (lower = more similar)
    """
    k = top_k or TOP_K_RESULTS
    collection = get_collection(collection_name)

    query_params: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": k,
        "include": ["documents", "metadatas", "distances"],
    }

    if filter_metadata:
        query_params["where"] = filter_metadata

    results = collection.query(**query_params)

    return _parse_results(results)


def _parse_results(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Parse ChromaDB query results into a clean list of dicts.
    """
    parsed = []

    if not raw or not raw.get("documents"):
        return parsed

    documents  = raw["documents"][0]
    metadatas  = raw["metadatas"][0]
    distances  = raw["distances"][0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        parsed.append({
            "text":        doc,
            "source":      meta.get("source", "unknown"),
            "page":        meta.get("page", 0),
            "chunk_index": meta.get("chunk_index", 0),
            "doc_type":    meta.get("doc_type", "unknown"),
            "score":       round(dist, 4),
        })

    return parsed


def collection_stats(collection_name: str | None = None) -> dict[str, Any]:
    """
    Return basic statistics about a collection.

    Useful for verifying ingestion completeness.
    """
    collection = get_collection(collection_name)
    count = collection.count()
    return {
        "collection": collection.name,
        "total_chunks": count,
    }


def _make_chunk_id(source: str, chunk_index: int) -> str:
    """
    Generate a deterministic, unique ID for a chunk.
    Uses an MD5 hash of source + chunk_index to keep IDs compact.
    """
    raw = f"{source}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def _build_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    """
    Build the metadata dict for ChromaDB storage.
    All values must be str, int, float, or bool — no nested objects.
    """
    meta: dict[str, Any] = {
        "source":      str(chunk.get("source", "")),
        "page":        int(chunk.get("page", 0)),
        "chunk_index": int(chunk.get("chunk_index", 0)),
        "doc_type":    str(chunk.get("doc_type", "")),
    }
    if "section" in chunk:
        meta["section"] = str(chunk["section"])
    return meta