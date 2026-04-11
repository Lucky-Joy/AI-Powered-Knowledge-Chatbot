"""
Central configuration for the Banking RAG Knowledge Assistant — KnowSure.
All tunable parameters are defined here. No hardcoding across modules.
"""

import os
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Document storage ──────────────────────────────────────────────────────────
DOCUMENTS_DIR = BASE_DIR / "raw_docs"

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = str(BASE_DIR / "chroma_db")

CHROMA_COLLECTIONS = {
    "default":    "banking_knowledge",
    "rbi":        "rbi_circulars",
    "sop":        "sop_documents",
    "compliance": "compliance_policies",
}
ACTIVE_COLLECTION = CHROMA_COLLECTIONS["default"]

# ── Embedding model ───────────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MIN_CHUNK_LENGTH = 50

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K_RESULTS = 5

# ── Language model ────────────────────────────────────────────────────────────
# Options: "groq" | "gemini" | "anthropic"
LLM_PROVIDER = "groq"
MAX_TOKENS = 1024

# ── Confidence & Validation ───────────────────────────────────────────────────
# Hyperparameter: cosine similarity threshold below which SME escalation triggers.
# Range: 0.0 (escalate everything) to 1.0 (never escalate).
# Default 0.75 — tune based on observed retrieval quality.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.60"))

# Minimum number of retrieved chunks required to attempt an answer
MIN_CHUNKS_REQUIRED = 1

# ── SME Cache ─────────────────────────────────────────────────────────────────
SME_CACHE_DB_PATH = str(BASE_DIR / "database" / "sme_cache.db")

# Similarity threshold for SME cache lookup (how similar a new query must be
# to a cached question to return the cached answer)
SME_CACHE_SIMILARITY_THRESHOLD = float(os.getenv("SME_CACHE_SIMILARITY_THRESHOLD", "0.92"))

# ── Audit Log ─────────────────────────────────────────────────────────────────
AUDIT_DB_PATH = str(BASE_DIR / "database" / "audit_log.db")

# ── Document Registry ─────────────────────────────────────────────────────────
DOCUMENT_REGISTRY_PATH = str(BASE_DIR / "data" / "document_registry.json")

# ── OCR ───────────────────────────────────────────────────────────────────────
OCR_LANGUAGE = "eng"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FILE = BASE_DIR / "system.log"
