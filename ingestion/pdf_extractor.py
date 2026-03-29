"""
PDF text extractor.

Handles two cases:
  1. Text-based PDFs  → extract text directly using PyMuPDF (fitz)
  2. Scanned PDFs     → fall back to OCR via pytesseract on rendered page images

Each page produces a dict with:
  {
      "text":      str,
      "source":    str,   # filename
      "page":      int,   # 1-indexed
      "doc_type":  "pdf"
  }
"""

from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from utils.logger import get_logger

logger = get_logger(__name__)

# Minimum character count for a page to be considered text-based
# Pages with fewer characters are assumed to be scanned/image pages
_TEXT_THRESHOLD = 50


def extract(file_path: str | Path) -> list[dict[str, Any]]:
    """
    Extract text from a PDF file, page by page.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        List of page-level dicts containing text and metadata.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error("PDF file not found: %s", file_path)
        return []

    pages: list[dict[str, Any]] = []

    try:
        doc = fitz.open(str(file_path))
        logger.info("Opened PDF: %s (%d pages)", file_path.name, len(doc))

        for page_index in range(len(doc)):
            page = doc[page_index]
            text = page.get_text("text").strip()

            if len(text) < _TEXT_THRESHOLD:
                # Likely a scanned page — use OCR
                text = _ocr_page(page, file_path.name, page_index + 1)

            if text:
                pages.append({
                    "text":     text,
                    "source":   file_path.name,
                    "page":     page_index + 1,
                    "doc_type": "pdf",
                })

        doc.close()
        logger.info("Extracted %d pages from %s", len(pages), file_path.name)

    except Exception as exc:
        logger.error("Failed to extract PDF %s: %s", file_path.name, exc)

    return pages


def _ocr_page(page: fitz.Page, source_name: str, page_number: int) -> str:
    """
    Render a PDF page to an image and run OCR on it.

    Falls back gracefully if pytesseract or Pillow is not installed.
    """
    try:
        import pytesseract
        from PIL import Image
        import io
        from config.settings import OCR_LANGUAGE

        # Render page at 2x resolution for better OCR accuracy
        matrix = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")

        image = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(image, lang=OCR_LANGUAGE).strip()

        if text:
            logger.debug(
                "OCR extracted %d chars from page %d of %s",
                len(text), page_number, source_name
            )
        return text

    except ImportError:
        logger.warning(
            "pytesseract or Pillow not installed. Skipping OCR for page %d of %s.",
            page_number, source_name
        )
        return ""
    except Exception as exc:
        logger.error(
            "OCR failed for page %d of %s: %s", page_number, source_name, exc
        )
        return ""