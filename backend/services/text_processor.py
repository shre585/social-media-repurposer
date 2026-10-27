"""TXT / MD / DOCX / PDF -> text, then split into 'units' the analyser can work with."""
import re
from pathlib import Path

from services.pdf_processor import extract_pdf


def read_document(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        text = extract_pdf(path)
    elif ext == ".docx":
        from docx import Document

        doc = Document(str(path))
        parts = []
        for p in doc.paragraphs:                       # keep Word headings so topics follow the document structure
            if not p.text.strip():
                continue
            style = (p.style.name or "") if p.style is not None else ""
            parts.append(f"## {p.text.strip()}" if style.lower().startswith(("heading", "title")) else p.text)
        text = "\n\n".join(parts)
    else:
        raw = path.read_bytes()
        for enc in ("utf-8", "utf-16", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 40:
        raise ValueError("The document is too short to repurpose.")
    return text


def to_units(text: str, min_words: int = 40) -> list[dict]:
    """Paragraph-level units (no timestamps). Short paragraphs are merged together."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units, buf = [], ""
    for p in paras:
        buf = f"{buf}\n{p}".strip()
        if len(buf.split()) >= min_words:
            units.append({"start": None, "end": None, "text": buf})
            buf = ""
    if buf:
        if units:
            units[-1]["text"] += "\n" + buf
        else:
            units.append({"start": None, "end": None, "text": buf})
    return units
