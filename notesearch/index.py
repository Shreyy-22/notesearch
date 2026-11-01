"""The search engine core: an inverted index with BM25 ranking.

DSA used here
  * Inverted index   term -> {doc_id: [positions]}   (hash maps + sorted position lists)
  * Set intersection AND queries and phrase candidates
  * Phrase matching  position lists checked at offsets p, p+1, p+2 ...
  * BM25             ranking by term frequency, rarity (idf) and doc length
  * Min/max heap     heapq.nlargest picks the top-k without sorting everything
  * Trie             prefix completion        (see trie.py)
  * BK-tree          typo tolerance           (see bktree.py)
"""
from __future__ import annotations

import heapq
import math
import random
import re
from dataclasses import dataclass

from .bktree import BKTree
from .query import Query, parse_query
from .tokenizer import terms, tokenize
from .trie import Trie


@dataclass
class Document:
    id: int
    path: str
    title: str
    text: str
    mtime: float
    size: int
    length: int            # number of tokens
    title_terms: frozenset


@dataclass
class Hit:
    doc: Document
    score: float
    positions: list[int]   # token positions that matched (for highlighting)


class SearchIndex:
    K1 = 1.5               # BM25: how fast repeated terms saturate
    B = 0.75               # BM25: how strongly long docs are penalised
    TITLE_BOOST = 0.5
    PHRASE_BOOST = 1.5

    def __init__(self):
        self.postings: dict[str, dict[int, list[int]]] = {}
        self.docs: dict[int, Document] = {}
        self.path_to_id: dict[str, int] = {}
        self.total_tokens = 0
        self._next_id = 0
        self._trie: Trie | None = None
        self._bk: BKTree | None = None

    # Trie / BK-tree are cheap to rebuild and awkward to pickle, so they are not saved.
    def __getstate__(self):
        state = self.__dict__.copy()
        state["_trie"] = state["_bk"] = None
        return state

    def __len__(self):
        return len(self.docs)

    def get(self, path: str) -> Document | None:
        i = self.path_to_id.get(path)
        return self.docs.get(i) if i is not None else None

    # ---------------------------------------------------------------- indexing
    def add(self, path: str, text: str, title: str | None = None,
            mtime: float = 0.0, size: int = 0) -> int:
        if path in self.path_to_id:
            self.remove(path)
        doc_id, self._next_id = self._next_id, self._next_id + 1
        toks = terms(text)
        title = title or path
        doc = Document(doc_id, path, title, text, mtime, size, len(toks),
                       frozenset(terms(title)))
        self.docs[doc_id] = doc
        self.path_to_id[path] = doc_id
        self.total_tokens += len(toks)
        for pos, t in enumerate(toks):
            self.postings.setdefault(t, {}).setdefault(doc_id, []).append(pos)
        self._trie = self._bk = None
        return doc_id

    def remove(self, path: str) -> bool:
        doc_id = self.path_to_id.pop(path, None)
        if doc_id is None:
            return False
        doc = self.docs.pop(doc_id)
        self.total_tokens -= doc.length
        for t in set(terms(doc.text)):
            plist = self.postings.get(t)
            if plist is not None:
                plist.pop(doc_id, None)
                if not plist:
                    del self.postings[t]
        self._trie = self._bk = None
        return True

    # -------------------------------------------------------------- vocabulary
    def _vocab(self) -> tuple[Trie, BKTree]:
        if self._trie is None or self._bk is None:
            trie, bk = Trie(), BKTree()
            words = list(self.postings)
            random.Random(0).shuffle(words)  # random insert order keeps the BK-tree balanced
            for w in words:
                trie.insert(w, sum(len(p) for p in self.postings[w].values()))
                bk.add(w)
            self._trie, self._bk = trie, bk
        return self._trie, self._bk

    def expand(self, term: str, prefix: bool = False, fuzzy: bool = True) -> dict[str, float]:
        """Map a query term to {indexed_term: weight}: exact > prefix > typo."""
        out: dict[str, float] = {}
        if term in self.postings:
            out[term] = 1.0
        if prefix:
            for w in self._vocab()[0].complete(term, 20):
                out.setdefault(w, 0.6)
        if not out and fuzzy and len(term) >= 3:
            max_d = 1 if len(term) <= 4 else 2   # a swapped pair of letters costs 2 edits
            for w, d in self._vocab()[1].search(term, max_d):
                out[w] = 1.0 - 0.3 * d
        return out

    def suggest(self, text: str, k: int = 5) -> list[str]:
        """Autocomplete the last word of a partially typed query."""
        m = re.search(r"\w+$", text)
        if not m:
            return []
        head, frag = text[:m.start()], m.group().lower()
        return [head + w for w in self._vocab()[0].complete(frag, k + 1) if w != frag][:k]

    # ------------------------------------------------------------------ search
    def _phrase_matches(self, phrase: list[str]) -> dict[int, list[int]]:
        """doc_id -> start positions where the whole phrase occurs consecutively."""
        lists = [self.postings.get(t) for t in phrase]
        if any(l is None for l in lists):
            return {}
        common = set(lists[0]).intersection(*lists[1:])
        out = {}
        for d in common:
            rest = [set(l[d]) for l in lists[1:]]
            starts = [p for p in lists[0][d]
                      if all((p + i + 1) in s for i, s in enumerate(rest))]
            if starts:
                out[d] = starts
        return out

    def _idf(self, df: int) -> float:
        n = len(self.docs)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _bm25(self, tf: int, df: int, doc_len: int, avg_len: float) -> float:
        norm = tf + self.K1 * (1 - self.B + self.B * doc_len / avg_len)
        return self._idf(df) * tf * (self.K1 + 1) / norm

    def search(self, query: str | Query, k: int = 10, fuzzy: bool = True,
               prefix: bool = False, match_all: bool = True) -> list[Hit]:
        q = parse_query(query) if isinstance(query, str) else query
        if not self.docs or not (q.terms or q.phrases):
            return []

        clauses = [self.expand(t, prefix=prefix and i == len(q.terms) - 1, fuzzy=fuzzy)
                   for i, t in enumerate(q.terms)]
        if match_all:
            if any(not c for c in clauses):
                return []
        else:
            clauses = [c for c in clauses if c]

        phrase_hits = [self._phrase_matches(p) for p in q.phrases]
        if any(not ph for ph in phrase_hits):
            return []

        # Candidate documents via set intersection.
        clause_docs = [set().union(*(self.postings[t].keys() for t in c)) for c in clauses]
        sets = [set(ph) for ph in phrase_hits]
        if clause_docs:
            sets.extend(clause_docs if match_all else [set().union(*clause_docs)])
        if not sets:
            return []
        cand = set.intersection(*sets)

        # Exclusions: -word and -"some phrase".
        for t in q.not_terms:
            cand.difference_update(self.postings.get(t, {}))
        for p in q.not_phrases:
            cand.difference_update(self._phrase_matches(p))

        # Score with BM25 (+ title and phrase boosts).
        avg = (self.total_tokens / len(self.docs)) or 1.0
        scores: dict[int, float] = {}
        for d in cand:
            doc, s = self.docs[d], 0.0
            for clause in clauses:
                for t, w in clause.items():
                    plist = self.postings[t].get(d)
                    if plist:
                        df = len(self.postings[t])
                        s += w * self._bm25(len(plist), df, doc.length, avg)
                        if t in doc.title_terms:
                            s += w * self.TITLE_BOOST * self._idf(df)
            for ph in phrase_hits:
                s += self.PHRASE_BOOST * self._bm25(len(ph[d]), len(ph), doc.length, avg)
            scores[d] = s

        # Top-k with a heap: O(n log k) instead of sorting all n candidates.
        top = heapq.nlargest(k, scores.items(), key=lambda kv: (kv[1], -kv[0]))

        hits = []
        for d, s in top:
            pos: set[int] = set()
            for clause in clauses:
                for t in clause:
                    pos.update(self.postings[t].get(d, ()))
            for p, ph in zip(q.phrases, phrase_hits):
                for st in ph.get(d, ()):
                    pos.update(range(st, st + len(p)))
            hits.append(Hit(self.docs[d], s, sorted(pos)))
        return hits
