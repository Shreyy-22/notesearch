"""Read .txt / .md / .pdf files into (title, text)."""
from __future__ import annotations

import re
from pathlib import Path

SUPPORTED = {".txt", ".md", ".markdown", ".pdf"}
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.M)


def load_file(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("PDF support needs: pip install pypdf") from e
        text = "\n\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        return path.stem, text
    text = path.read_text(encoding="utf-8", errors="replace")
    if ext in {".md", ".markdown"}:
        m = _HEADING.search(text)
        if m:
            return m.group(1), text
    return path.stem, text
