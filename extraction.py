"""
Text extraction for pattern documents.

Word (.docx): python-docx, paragraphs + table cells in document order.
PDF (.pdf): pdfplumber for the native text layer; any page that comes back
near-empty is treated as scanned/image-based and re-rendered to an image
(pdf2image) for OCR (pytesseract). Each OCR'd page is noted in warnings so
the report can tell the user "page 3 was OCR'd, double-check it."
"""

from __future__ import annotations
import os

OCR_MIN_CHARS = 20  # below this, a PDF page is treated as having no real text layer


def extract_text(path: str) -> tuple[str, list[str]]:
    """Returns (full_text, warnings). Raises ValueError for unsupported file types."""
    lower = path.lower()
    if lower.endswith(".docx"):
        return _extract_docx(path)
    if lower.endswith(".pdf"):
        return _extract_pdf(path)
    raise ValueError(f"Unsupported file type: {os.path.basename(path)} (expected .pdf or .docx)")


def _extract_docx(path: str) -> tuple[str, list[str]]:
    import docx

    doc = docx.Document(path)
    warnings: list[str] = []
    parts: list[str] = []

    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    if not parts:
        warnings.append("No extractable text found in this Word document.")

    return "\n".join(parts), warnings


def _extract_pdf(path: str) -> tuple[str, list[str]]:
    import pdfplumber

    warnings: list[str] = []
    page_texts: list[str] = []
    ocr_pages: list[int] = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < OCR_MIN_CHARS:
                ocr_text = _ocr_page(path, i)
                if ocr_text.strip():
                    page_texts.append(ocr_text)
                    ocr_pages.append(i)
                else:
                    page_texts.append(text)
            else:
                page_texts.append(text)

    if ocr_pages:
        pages_str = ", ".join(str(p) for p in ocr_pages)
        warnings.append(
            f"Page(s) {pages_str} had little or no extractable text layer and were "
            f"read with OCR instead -- double-check those pages, OCR can misread "
            f"stitch counts and abbreviations."
        )

    full_text = "\n\n".join(page_texts)
    if not full_text.strip():
        warnings.append("No extractable text found anywhere in this PDF, including via OCR.")

    return full_text, warnings


def _ocr_page(path: str, page_number: int) -> str:
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(path, first_page=page_number, last_page=page_number, dpi=300)
    if not images:
        return ""
    return pytesseract.image_to_string(images[0])
