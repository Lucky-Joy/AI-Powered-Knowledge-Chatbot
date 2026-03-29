"""
SME Cache — KnowSure.

When a query is escalated to an SME and the SME provides a verified answer,
that answer is stored here. Future similar queries check this cache first
before hitting the vector database — reducing SME dependency over time.

Similarity between a new query and cached queries is computed using
cosine similarity of their embeddings.

Uses SQLite for storage — no additional dependencies.
"""

from __future__ import annotations
import sqlite3
import json
import numpy as np
from datetime import datetime
from pathlib import Path

from config.settings import SME_CACHE_DB_PATH, SME_CACHE_SIMILARITY_THRESHOLD
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_connection() -> sqlite3.Connection:
    Path(SME_CACHE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SME_CACHE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db() -> None:
    """Create the sme_cache table if it does not exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sme_cache (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                query         TEXT    NOT NULL,
                query_embedding TEXT  NOT NULL,
                sme_answer    TEXT    NOT NULL,
                sources       TEXT,
                added_by      TEXT    DEFAULT 'SME'
            )
        """)
        conn.commit()
    logger.info("SME Cache DB initialized at: %s", SME_CACHE_DB_PATH)


def store_sme_answer(
    query: str,
    query_embedding: list[float],
    sme_answer: str,
    sources: list[str] | None = None,
    added_by: str = "SME",
) -> int:
    """
    Store a verified SME answer for a query.

    Args:
        query:           The original user query.
        query_embedding: The embedding vector of the query.
        sme_answer:      The verified answer provided by the SME.
        sources:         Optional source citations.
        added_by:        Identifier of who added the answer.

    Returns:
        Row ID of the inserted record.
    """
    initialize_db()

    with _get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO sme_cache (timestamp, query, query_embedding, sme_answer, sources, added_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(sep=" ", timespec="seconds"),
            query,
            json.dumps(query_embedding),
            sme_answer,
            json.dumps(sources or []),
            added_by,
        ))
        conn.commit()
        row_id = cursor.lastrowid

    logger.info("SME answer cached (ID=%d) for query: '%s'", row_id, query[:60])
    return row_id


def find_cached_answer(
    query_embedding: list[float],
    threshold: float | None = None,
) -> dict | None:
    """
    Search the SME cache for a similar previously-answered query.

    Uses cosine similarity between the new query embedding and all
    cached query embeddings. Returns the best match if above threshold.

    Args:
        query_embedding: Embedding of the current query.
        threshold:       Similarity threshold override. Defaults to
                         SME_CACHE_SIMILARITY_THRESHOLD from settings.

    Returns:
        Dict with sme_answer, sources, similarity_score, original_query
        if a match is found, else None.
    """
    initialize_db()
    effective_threshold = threshold if threshold is not None else SME_CACHE_SIMILARITY_THRESHOLD

    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, query, query_embedding, sme_answer, sources FROM sme_cache"
        ).fetchall()

    if not rows:
        return None

    query_vec = np.array(query_embedding, dtype=np.float32)
    best_score = -1.0
    best_row = None

    for row in rows:
        try:
            cached_vec = np.array(json.loads(row["query_embedding"]), dtype=np.float32)
            # Cosine similarity
            score = float(
                np.dot(query_vec, cached_vec) /
                (np.linalg.norm(query_vec) * np.linalg.norm(cached_vec) + 1e-10)
            )
            if score > best_score:
                best_score = score
                best_row = row
        except Exception as exc:
            logger.warning("SME cache similarity error for row %d: %s", row["id"], exc)

    if best_score >= effective_threshold and best_row is not None:
        logger.info(
            "SME cache HIT (similarity=%.4f) for cached query: '%s'",
            best_score, best_row["query"][:60],
        )
        try:
            sources = json.loads(best_row["sources"]) if best_row["sources"] else []
        except Exception:
            sources = []

        return {
            "sme_answer":      best_row["sme_answer"],
            "sources":         sources,
            "similarity_score": round(best_score, 4),
            "original_query":  best_row["query"],
        }

    logger.info("SME cache MISS (best similarity=%.4f, threshold=%.4f).", best_score, effective_threshold)
    return None


def get_all_cached(limit: int = 100) -> list[dict]:
    """Return all cached SME answers (without embeddings) for display."""
    initialize_db()
    with _get_connection() as conn:
        rows = conn.execute("""
            SELECT id, timestamp, query, sme_answer, sources, added_by
            FROM sme_cache
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["sources"] = json.loads(d["sources"]) if d["sources"] else []
        except Exception:
            d["sources"] = []
        result.append(d)
    return result