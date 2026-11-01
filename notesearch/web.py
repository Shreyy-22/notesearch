from __future__ import annotations

import heapq
import time
from collections import Counter
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from .highlight import make_snippet, render_full_html, render_html
from .notebook import Notebook

WEB_DIR = Path(__file__).with_name("web")

# Only used to keep the "most used words" card interesting; search itself never drops words.
_STOP = set("""a about after all also an and any are as at be been but by can could did do does for from
had has have he her his how i if in into is it its just may more most my no not of on one or our out
over she so some such than that the their them then there these they this to up was we were what when
which who will with would you your""".split())


def _flag(name: str, default: bool) -> bool:
    v = request.args.get(name)
    return default if v is None else v.lower() in ("1", "true", "yes", "on")


def _ext(path: str) -> str:
    s = Path(path).suffix.lower().lstrip(".")
    return "md" if s == "markdown" else s


def create_app(nb: Notebook) -> Flask:
    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="/static")

    def search_options() -> dict:
        return dict(prefix=_flag("prefix", False), fuzzy=_flag("fuzzy", True),
                    match_all=not _flag("any", False))

    @app.get("/")
    def home():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/api/search")
    def search():
        q = request.args.get("q", "").strip()
        k = min(max(request.args.get("k", 10, type=int), 1), 50)
        types = {t for t in request.args.get("types", "").lower().split(",") if t}
        start = time.perf_counter()
        hits = []
        if q:
            # when filtering by file type, rank everything first, then filter, then cut to k
            hits = nb.search(q, k=max(len(nb.index), 1) if types else k, **search_options())
            if types:
                hits = [h for h in hits if _ext(h.doc.path) in types]
            hits = hits[:k]
        took = (time.perf_counter() - start) * 1000
        top = max((h.score for h in hits), default=1.0) or 1.0
        if request.args.get("sort") == "newest":
            hits = sorted(hits, key=lambda h: h.doc.mtime, reverse=True)
        return jsonify(
            took_ms=round(took, 2),
            results=[{"title": h.doc.title, "path": h.doc.path, "type": _ext(h.doc.path),
                      "score": round(h.score, 3), "relative": round(h.score / top, 3),
                      "words": h.doc.length, "modified": h.doc.mtime,
                      "snippet": render_html(make_snippet(h.doc, h.positions))}
                     for h in hits])

    @app.get("/api/suggest")
    def suggest():
        return jsonify(suggestions=nb.suggest(request.args.get("q", "")))

    @app.get("/api/doc")
    def doc():
        """One whole note, with the words of the current query highlighted."""
        path = request.args.get("path", "")
        q = request.args.get("q", "").strip()
        with nb.lock:
            d = nb.index.get(path)          # looked up in the index, never on disk
            if d is None:
                return jsonify(error="Note not found"), 404
            positions: list[int] = []
            if q:
                for h in nb.index.search(q, k=max(len(nb.index), 1), **search_options()):
                    if h.doc.id == d.id:
                        positions = h.positions
                        break
            return jsonify(title=d.title, path=d.path, type=_ext(d.path), words=d.length,
                           modified=d.mtime, matches=len(positions),
                           html=render_full_html(d, positions))

    @app.get("/api/notes")
    def notes():
        with nb.lock:
            items = [{"path": d.path, "title": d.title, "type": _ext(d.path),
                      "words": d.length, "modified": d.mtime}
                     for d in nb.index.docs.values()]
        items.sort(key=lambda n: n["title"].lower())
        return jsonify(notes=items)

    @app.get("/api/overview")
    def overview():
        with nb.lock:
            ix = nb.index
            docs = list(ix.docs.values())
            freq = ((sum(len(p) for p in plist.values()), w) for w, plist in ix.postings.items()
                    if len(w) >= 3 and w not in _STOP and not w.isdigit())
            top_words = heapq.nsmallest(12, freq, key=lambda t: (-t[0], t[1]))
            recent = sorted(docs, key=lambda d: d.mtime, reverse=True)[:5]
            data = dict(
                folder=nb.root.name, notes=len(docs), unique_words=len(ix.postings),
                total_words=ix.total_tokens,
                types=dict(Counter(_ext(d.path) for d in docs)),
                top_words=[{"word": w, "count": c} for c, w in top_words],
                recent=[{"path": d.path, "title": d.title, "type": _ext(d.path),
                         "words": d.length, "modified": d.mtime} for d in recent],
                index_kb=round(nb.index_file.stat().st_size / 1024, 1) if nb.index_file.exists() else 0)
        return jsonify(data)

    @app.post("/api/reindex")
    def reindex():
        s = nb.sync()
        return jsonify(added=s.added, updated=s.updated, removed=s.removed,
                       unchanged=s.unchanged, errors=s.errors)

    @app.get("/api/stats")
    def stats():
        ix = nb.index
        return jsonify(folder=nb.root.name, notes=len(ix), terms=len(ix.postings),
                       tokens=ix.total_tokens)

    return app
