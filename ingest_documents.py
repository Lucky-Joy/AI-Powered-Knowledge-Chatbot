"""
Document ingestion entry point.

Run this script once (or whenever new documents are added) to:
  1. Extract text from all documents in data/documents/
  2. Chunk the extracted text with overlap
  3. Generate embeddings for each chunk
  4. Store embeddings and metadata in ChromaDB

Usage:
    python ingest_documents.py
    python ingest_documents.py --dir /path/to/custom/documents
    python ingest_documents.py --collection rbi_circulars

After ingestion, run the UI:
    python interface/app.py
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Ensure the project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import DOCUMENTS_DIR, ACTIVE_COLLECTION
from ingestion.ingestion_pipeline import ingest_directory
from processing.chunker import chunk_pages
from embeddings.embedder import embed_chunks
from vectorstore.chroma_store import store_chunks, collection_stats
from utils.logger import get_logger

logger = get_logger("ingest_documents")


def run_ingestion(documents_dir: str, collection_name: str) -> None:
    """
    Execute the full ingestion pipeline for a documents directory.

    Args:
        documents_dir:   Path to the directory containing documents to ingest.
        collection_name: ChromaDB collection to store embeddings in.
    """
    logger.info("=" * 60)
    logger.info("Banking RAG — Document Ingestion Pipeline")
    logger.info("=" * 60)
    logger.info("Documents directory : %s", documents_dir)
    logger.info("Target collection   : %s", collection_name)

    # ── Step 1: Ingest and extract text ──────────────────────────────────────
    logger.info("[1/4] Ingesting documents...")
    pages = ingest_directory(documents_dir)

    if not pages:
        logger.error(
            "No documents were extracted. Check that supported files exist in: %s",
            documents_dir
        )
        sys.exit(1)

    logger.info("Extracted %d page/section(s) from documents.", len(pages))

    # ── Step 2: Chunk the extracted text ─────────────────────────────────────
    logger.info("[2/4] Chunking extracted text...")
    chunks = chunk_pages(pages)

    if not chunks:
        logger.error("No chunks produced. Check chunking configuration.")
        sys.exit(1)

    logger.info("Produced %d chunk(s) from extracted text.", len(chunks))

    # ── Step 3: Generate embeddings ───────────────────────────────────────────
    logger.info("[3/4] Generating embeddings (this may take a moment)...")
    chunks = embed_chunks(chunks)
    logger.info("Embeddings generated for %d chunk(s).", len(chunks))

    # ── Step 4: Store in ChromaDB ─────────────────────────────────────────────
    logger.info("[4/4] Storing chunks in ChromaDB collection '%s'...", collection_name)
    store_chunks(chunks, collection_name=collection_name)

    # ── Summary ───────────────────────────────────────────────────────────────
    stats = collection_stats(collection_name)
    logger.info("=" * 60)
    logger.info("Ingestion complete.")
    logger.info(
        "Collection '%s' now contains %d chunk(s).",
        stats["collection"], stats["total_chunks"]
    )
    logger.info("=" * 60)
    logger.info("You can now start the assistant: python interface/app.py")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest documents into the Banking RAG knowledge base."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=str(DOCUMENTS_DIR),
        help="Path to the documents directory (default: data/documents/)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=ACTIVE_COLLECTION,
        help=f"ChromaDB collection name (default: {ACTIVE_COLLECTION})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_ingestion(
        documents_dir=args.dir,
        collection_name=args.collection,
    )