from __future__ import annotations
from typing import Any
from sentence_transformers import SentenceTransformer
from config.settings import EMBEDDING_MODEL_NAME
from utils.logger import get_logger

logger = get_logger(__name__)

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded successfully.")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    logger.info("Generating embeddings for %d text(s)...", len(texts))

    # BGE models require a query instruction prefix for better retrieval
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,   # BGE requires normalized embeddings
    )
    logger.info("Embedding generation complete.")
    return [emb.tolist() for emb in embeddings]


def embed_query(query: str) -> list[float]:
    """
    BGE models use an instruction prefix for queries (not for documents).
    This improves retrieval accuracy significantly.
    """
    if not query.strip():
        raise ValueError("Query text cannot be empty.")

    model = _get_model()

    # BGE-specific query instruction prefix
    instruction = "Represent this sentence for searching relevant passages: "
    prefixed_query = instruction + query

    import numpy as np
    embedding = model.encode(
        prefixed_query,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embedding.tolist()


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_texts(texts)
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding
    return chunks