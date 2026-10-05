"""PDF -> plain text."""
from pathlib import Path


def extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as e:
            raise ValueError("This PDF is password protected.") from e
    pages = [(p.extract_text() or "").strip() for p in reader.pages]
    text = "\n\n".join(p for p in pages if p)
    if len(text) < 50:
        raise ValueError("No readable text found. This looks like a scanned PDF (images only) - OCR is not enabled yet.")
    return text
