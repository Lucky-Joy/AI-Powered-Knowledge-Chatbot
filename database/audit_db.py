"""
Audit log database — KnowSure.

Every query, response, confidence score, sources retrieved,
and escalation decision is recorded here for governance and compliance.

Uses SQLite — no additional dependencies required.
"""

from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from pathlib import Path

from config.settings import AUDIT_DB_PATH
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the audit database, creating it if needed."""
    Path(AUDIT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(AUDIT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db() -> None:
    """Create the audit_log table if it does not exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp        TEXT    NOT NULL,
                query            TEXT    NOT NULL,
                collection       TEXT,
                confidence_score REAL,
                confidence_label TEXT,
                escalated        INTEGER DEFAULT 0,
                sources          TEXT,
                answer_snippet   TEXT,
                llm_provider     TEXT,
                retrieval_ms     REAL,
                llm_ms           REAL,
                total_ms         REAL
            )
        """)
        conn.commit()
    logger.info("Audit DB initialized at: %s", AUDIT_DB_PATH)


def log_query(
    query: str,
    collection: str,
    confidence_score: float,
    confidence_label: str,
    escalated: bool,
    sources: list[str],
    answer_snippet: str,
    llm_provider: str,
    retrieval_ms: float = 0.0,
    llm_ms: float = 0.0,
    total_ms: float = 0.0,
) -> int:
    """
    Write a query event to the audit log.

    Returns:
        The row ID of the inserted record.
    """
    initialize_db()

    with _get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO audit_log (
                timestamp, query, collection,
                confidence_score, confidence_label, escalated,
                sources, answer_snippet, llm_provider,
                retrieval_ms, llm_ms, total_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(sep=" ", timespec="seconds"),
            query,
            collection,
            round(confidence_score, 4),
            confidence_label,
            1 if escalated else 0,
            json.dumps(sources),
            answer_snippet[:300] if answer_snippet else "",
            llm_provider,
            round(retrieval_ms, 1),
            round(llm_ms, 1),
            round(total_ms, 1),
        ))
        conn.commit()
        row_id = cursor.lastrowid

    logger.info("Audit log entry #%d recorded.", row_id)
    return row_id


def get_recent_logs(limit: int = 50) -> list[dict]:
    """
    Retrieve the most recent audit log entries.

    Args:
        limit: Maximum number of rows to return.

    Returns:
        List of dicts representing audit log rows, newest first.
    """
    initialize_db()

    with _get_connection() as conn:
        rows = conn.execute("""
            SELECT id, timestamp, query, collection,
                   confidence_score, confidence_label, escalated,
                   sources, answer_snippet, llm_provider,
                   retrieval_ms, llm_ms, total_ms
            FROM audit_log
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


def get_escalation_count() -> int:
    """Return total number of escalated queries."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM audit_log WHERE escalated = 1"
        ).fetchone()
        return row["cnt"] if row else 0


def get_summary_stats() -> dict:
    """Return summary statistics for the audit dashboard."""
    initialize_db()
    with _get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)                        AS total_queries,
                SUM(escalated)                  AS total_escalations,
                AVG(confidence_score)           AS avg_confidence,
                AVG(total_ms)                   AS avg_response_ms
            FROM audit_log
        """).fetchone()

    if not row or row["total_queries"] == 0:
        return {
            "total_queries":     0,
            "total_escalations": 0,
            "avg_confidence":    0.0,
            "avg_response_ms":   0.0,
        }

    return {
        "total_queries":     row["total_queries"],
        "total_escalations": row["total_escalations"] or 0,
        "avg_confidence":    round(row["avg_confidence"] or 0.0, 4),
        "avg_response_ms":   round(row["avg_response_ms"] or 0.0, 1),
    }