"""
Image file OCR extractor.

Supports: .png, .jpg, .jpeg, .tiff, .bmp

Used for scanned documents that arrive as standalone image files
(as opposed to image-embedded PDFs which are handled by pdf_extractor).

Preprocessing steps are applied before OCR to improve accuracy on
low-quality scans common in banking document archives.
"""

from pathlib import Path
from typing import Any
import PIL

from utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}


def extract(file_path: str | Path) -> list[dict[str, Any]]:
    """
    Run OCR on an image file and return extracted text as a single section.

    Args:
        file_path: Path to the image file.

    Returns:
        List with a single dict containing OCR text and metadata,
        or empty list on failure.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        logger.error("Image file not found: %s", file_path)
        return []

    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        logger.warning(
            "Unsupported image format: %s. Skipping.", file_path.suffix
        )
        return []

    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageOps
        from config.settings import OCR_LANGUAGE

        image = Image.open(str(file_path))
        image = _preprocess(image)

        text = pytesseract.image_to_string(image, lang=OCR_LANGUAGE).strip()

        if not text:
            logger.warning("OCR produced no text for %s", file_path.name)
            return []

        logger.info(
            "OCR extracted %d chars from %s", len(text), file_path.name
        )
        return [{
            "text":     text,
            "source":   file_path.name,
            "page":     1,
            "doc_type": "image",
        }]

    except ImportError:
        logger.error(
            "pytesseract or Pillow not installed. Cannot process image: %s",
            file_path.name
        )
        return []
    except Exception as exc:
        logger.error("OCR failed for %s: %s", file_path.name, exc)
        return []


def _preprocess(image) -> "PIL.Image.Image":
    """
    Apply image preprocessing to improve OCR accuracy on scanned documents.

    Steps:
      1. Convert to greyscale
      2. Increase contrast (autocontrast)
      3. Apply light sharpening
    """
    from PIL import ImageFilter, ImageOps

    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)
    return image