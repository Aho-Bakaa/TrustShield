"""PDF handling: prefer embedded text; fall back to rendering page 1 for vision."""
from __future__ import annotations

from .log import get_logger

_log = get_logger("doc")

_MIN_TEXT = 40  # below this we treat the PDF as scanned and render it for vision


def pdf_to_text_or_image(data: bytes) -> tuple[str, bytes | None]:
    """Return (extracted_text, page_png_or_None).

    If the PDF has selectable text, return it. Otherwise render the first page
    to a PNG so the vision model can read a scanned/image PDF.
    """
    import fitz  # pymupdf

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in doc).strip()
        if len(text) >= _MIN_TEXT:
            _log.info("pdf: extracted %d chars of embedded text (%d pages)", len(text), doc.page_count)
            return text, None
        pix = doc[0].get_pixmap(dpi=150)
        png = pix.tobytes("png")
        _log.info("pdf: no embedded text (%d chars); rendered page 1 -> %d bytes png", len(text), len(png))
        return text, png
    finally:
        doc.close()
