"""A folder of notes + its saved index. Handles incremental syncing and persistence."""
from __future__ import annotations

import os
import pickle
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .index import Hit, SearchIndex
from .loaders import SUPPORTED, load_file

INDEX_VERSION = 1


@dataclass
class SyncStats:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.removed)


class Notebook:
    def __init__(self, root: str | os.PathLike, data_dir: str | os.PathLike | None = None):
        self.root = Path(root).expanduser().resolve()
        self.data_dir = Path(data_dir) if data_dir else self.root / ".notesearch"
        self.index_file = self.data_dir / "index.pkl"
        self.lock = threading.RLock()
        self.index = self._load()

    # ------------------------------------------------------------ persistence
    def _load(self) -> SearchIndex:
        try:
            with open(self.index_file, "rb") as f:
                blob = pickle.load(f)
            if blob.get("version") == INDEX_VERSION:
                return blob["index"]
        except Exception:
            pass                      # missing/corrupt/old index: just rebuild it
        return SearchIndex()

    def save(self) -> None:
        with self.lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.index_file.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump({"version": INDEX_VERSION, "index": self.index}, f,
                            protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, self.index_file)   # atomic: never leaves a half-written index

    # ------------------------------------------------------------------- sync
    def _scan(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                p = Path(dirpath) / name
                if not name.startswith(".") and p.suffix.lower() in SUPPORTED:
                    yield p

    def sync(self) -> SyncStats:
        """Bring the index in line with the folder. Only touches new/changed/deleted files."""
        stats = SyncStats()
        with self.lock:
            seen = set()
            for p in self._scan():
                rel = p.relative_to(self.root).as_posix()
                seen.add(rel)
                try:
                    st = p.stat()
                    old = self.index.get(rel)
                    if old and old.mtime == st.st_mtime and old.size == st.st_size:
                        stats.unchanged += 1
                        continue
                    title, text = load_file(p)
                    self.index.add(rel, text, title, st.st_mtime, st.st_size)
                    if old:
                        stats.updated += 1
                    else:
                        stats.added += 1
                except Exception as e:
                    stats.errors.append(f"{rel}: {e}")
            for rel in set(self.index.path_to_id) - seen:
                self.index.remove(rel)
                stats.removed += 1
            if stats.changed:
                self.save()
        return stats

    # ----------------------------------------------------------------- search
    def search(self, query: str, **kw) -> list[Hit]:
        with self.lock:
            return self.index.search(query, **kw)

    def suggest(self, text: str, k: int = 5) -> list[str]:
        with self.lock:
            return self.index.suggest(text, k)


class Watcher(threading.Thread):
    """Polls the folder (cheap: stat() only) and re-indexes whatever changed."""

    def __init__(self, nb: Notebook, interval: float = 2.0, on_change=None):
        super().__init__(daemon=True)
        self.nb, self.interval, self.on_change = nb, interval, on_change
        self._halt = threading.Event()

    def run(self):
        while not self._halt.wait(self.interval):
            stats = self.nb.sync()
            if stats.changed and self.on_change:
                self.on_change(stats)

    def stop(self):
        self._halt.set()
