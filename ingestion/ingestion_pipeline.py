"""
Document ingestion pipeline orchestrator.

Routes each document to the correct extractor based on file extension,
then returns a flat list of page/section dicts for downstream processing.

This is the single entry point for the ingestion layer. Adding support
for a new document type only requires registering a new extractor here.
"""

from pathlib import Path
from typing import Any

from ingestion import pdf_extractor, docx_extractor, xlsx_extractor, image_extractor
from utils.logger import get_logger

logger = get_logger(__name__)

# Maps file extensions to their extractor modules
_EXTRACTOR_REGISTRY: dict[str, Any] = {
    ".pdf":  pdf_extractor,
    ".docx": docx_extractor,
    ".xlsx": xlsx_extractor,
    ".png":  image_extractor,
    ".jpg":  image_extractor,
    ".jpeg": image_extractor,
    ".tiff": image_extractor,
    ".tif":  image_extractor,
    ".bmp":  image_extractor,
}


def ingest_file(file_path: str | Path) -> list[dict[str, Any]]:
    """
    Ingest a single document file.

    Args:
        file_path: Path to the document file.

    Returns:
        List of dicts, each representing a page or section with:
            - text     : extracted text
            - source   : filename
            - page     : page/section number
            - doc_type : format identifier
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    extractor = _EXTRACTOR_REGISTRY.get(ext)
    if extractor is None:
        logger.warning("No extractor registered for extension: %s", ext)
        return []

    logger.info("Ingesting: %s", file_path.name)
    pages = extractor.extract(file_path)
    logger.info(
        "Ingested %d section(s) from %s", len(pages), file_path.name
    )
    return pages


def ingest_directory(directory: str | Path) -> list[dict[str, Any]]:
    """
    Recursively ingest all supported documents from a directory.

    Args:
        directory: Path to the directory containing documents.

    Returns:
        Combined flat list of all extracted page/section dicts.
    """
    directory = Path(directory)
    if not directory.is_dir():
        logger.error("Directory not found: %s", directory)
        return []

    all_pages: list[dict[str, Any]] = []
    supported_extensions = set(_EXTRACTOR_REGISTRY.keys())

    files = [
        f for f in directory.rglob("*")
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]

    logger.info(
        "Found %d supported file(s) in %s", len(files), directory
    )

    for file_path in files:
        pages = ingest_file(file_path)
        all_pages.extend(pages)

    logger.info(
        "Total sections ingested from directory: %d", len(all_pages)
    )
    return all_pages