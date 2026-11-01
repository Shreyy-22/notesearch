import time
from pathlib import Path

import pytest

from notesearch import Notebook, SearchIndex
from notesearch.bktree import BKTree, levenshtein
from notesearch.highlight import make_snippet, render_html
from notesearch.query import parse_query
from notesearch.trie import Trie


@pytest.fixture
def ix():
    i = SearchIndex()
    i.add("graphs.md", "Breadth first search finds the shortest path in an unweighted graph. "
                       "Dijkstra finds the shortest path in a weighted graph.", "Graph algorithms")
    i.add("bs.md", "Binary search halves a sorted array. It runs in logarithmic time.", "Binary search")
    i.add("heap.md", "A heap gives the top k items. Dijkstra uses a priority queue heap.", "Heaps")
    return i


def test_levenshtein():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3
    assert levenshtein("same", "same") == 0


def test_bktree_matches_brute_force():
    words = ["graph", "grape", "graft", "giraffe", "heap", "help", "hello", "search", "beach", "binary"]
    bk = BKTree()
    for w in words:
        bk.add(w)
    for target in ["grahp", "hepa", "serch", "xyz"]:
        for d in (1, 2):
            expected = sorted((w, levenshtein(target, w)) for w in words if levenshtein(target, w) <= d)
            assert sorted(bk.search(target, d)) == expected


def test_trie_complete_ranks_by_frequency():
    t = Trie()
    t.insert("graph", 5); t.insert("grape", 1); t.insert("graphs", 3); t.insert("heap", 9)
    assert t.complete("gra", 2) == ["graph", "graphs"]
    assert t.complete("zzz") == []


def test_parse_query():
    q = parse_query('graph "shortest path" -weighted -"dead end"')
    assert q.terms == ["graph"]
    assert q.phrases == [["shortest", "path"]]
    assert q.not_terms == ["weighted"]
    assert q.not_phrases == [["dead", "end"]]


def test_basic_ranking(ix):
    hits = ix.search("dijkstra")
    assert {h.doc.path for h in hits} == {"graphs.md", "heap.md"}


def test_and_semantics_and_any(ix):
    assert [h.doc.path for h in ix.search("binary heap")] == []
    assert len(ix.search("binary heap", match_all=False)) == 2


def test_typo_tolerance(ix):
    assert ix.search("grahp")[0].doc.path == "graphs.md"
    assert ix.search("grahp", fuzzy=False) == []


def test_phrase(ix):
    assert [h.doc.path for h in ix.search('"shortest path"')] == ["graphs.md"]
    assert ix.search('"path shortest"') == []


def test_exclusion(ix):
    paths = {h.doc.path for h in ix.search("dijkstra -heap")}
    assert paths == {"graphs.md"}
    assert {h.doc.path for h in ix.search('dijkstra -"priority queue"')} == {"graphs.md"}


def test_title_boost():
    i = SearchIndex()
    i.add("a", "graph " + "filler " * 5, "Other")
    i.add("b", "graph " + "filler " * 5, "Graph")
    assert i.search("graph")[0].doc.path == "b"


def test_prefix_and_suggest(ix):
    assert ix.search("prior", prefix=True)[0].doc.path == "heap.md"
    assert "binary" in ix.suggest("bin")
    assert ix.suggest("graph ") == []


def test_remove_cleans_postings(ix):
    ix.remove("bs.md")
    assert ix.search("binary") == []
    assert "binary" not in ix.postings


def test_snippet_highlight(ix):
    h = ix.search("priority")[0]
    html = render_html(make_snippet(h.doc, h.positions))
    assert "<mark>priority</mark>" in html


def test_snippet_escapes_html():
    i = SearchIndex()
    i.add("x", "<script>alert(1)</script> hello world")
    h = i.search("hello")[0]
    assert "<script>" not in render_html(make_snippet(h.doc, h.positions))


def test_sync_incremental_and_persistence(tmp_path: Path):
    (tmp_path / "a.md").write_text("# Alpha\nhash tables are fast")
    (tmp_path / "b.txt").write_text("binary trees and heaps")
    nb = Notebook(tmp_path)
    s = nb.sync()
    assert (s.added, s.updated, s.removed) == (2, 0, 0)
    assert nb.sync().unchanged == 2

    time.sleep(0.01)
    (tmp_path / "a.md").write_text("# Alpha\nhash tables are very very fast")
    (tmp_path / "b.txt").unlink()
    (tmp_path / "c.md").write_text("new note about tries")
    s = nb.sync()
    assert (s.added, s.updated, s.removed) == (1, 1, 1)
    assert nb.search("tries")[0].doc.path == "c.md"
    assert nb.search("heaps") == []

    nb2 = Notebook(tmp_path)               # reload from disk, no re-scan needed
    assert nb2.search("tries")[0].doc.path == "c.md"
    assert nb2.sync().unchanged == 2


def test_hidden_dirs_ignored(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.md").write_text("secret")
    nb = Notebook(tmp_path)
    nb.sync()
    assert nb.search("secret") == []
