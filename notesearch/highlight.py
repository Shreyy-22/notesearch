"""Build a short snippet around the first match and render it with highlights."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .index import Document
from .tokenizer import tokenize


@dataclass
class Snippet:
    text: str
    marks: list[tuple[int, int]]   # (start, end) char ranges inside `text`
    head: bool                     # text was cut at the front
    tail: bool                     # text was cut at the end


def make_snippet(doc: Document, positions: list[int], width: int = 180) -> Snippet:
    text = doc.text
    toks = tokenize(text)
    valid = [p for p in positions if p < len(toks)]
    if not valid:
        return Snippet(re.sub(r"\s", " ", text[:width]).strip(), [], False, len(text) > width)

    _, s0, e0 = toks[valid[0]]
    start = max(0, s0 - width // 4)
    if start > 0:                                   # snap to a word boundary
        m = re.search(r"\s", text[start:s0])
        if m:
            start += m.end()
    end = min(len(text), start + width)
    if end < len(text):
        ws = max(text.rfind(" ", 0, end), text.rfind("\n", 0, end))
        if ws > e0:
            end = ws
    marks = [(toks[p][1] - start, toks[p][2] - start) for p in valid
             if toks[p][1] >= start and toks[p][2] <= end]
    chunk = re.sub(r"\s", " ", text[start:end])     # same length, so marks stay valid
    return Snippet(chunk, marks, start > 0, end < len(text))


def _render(sn: Snippet, wrap, escape) -> str:
    out, i = [], 0
    for a, b in sn.marks:
        out.append(escape(sn.text[i:a]))
        out.append(wrap(escape(sn.text[a:b])))
        i = b
    out.append(escape(sn.text[i:]))
    return ("…" if sn.head else "") + "".join(out) + ("…" if sn.tail else "")


def render_html(sn: Snippet) -> str:
    return _render(sn, lambda s: f"<mark>{s}</mark>", html.escape)


def render_ansi(sn: Snippet) -> str:
    return _render(sn, lambda s: f"\033[1;33m{s}\033[0m", lambda s: s)


def render_full_html(doc: Document, positions: list[int]) -> str:
    """The whole note as escaped HTML with every matched word wrapped in <mark>."""
    toks = tokenize(doc.text)
    marks = [(toks[p][1], toks[p][2]) for p in positions if p < len(toks)]
    return _render(Snippet(doc.text, marks, False, False),
                   lambda s: f"<mark>{s}</mark>", html.escape)
