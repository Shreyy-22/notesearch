import os

import pytest

flask = pytest.importorskip("flask")

from notesearch import Notebook
from notesearch.web import create_app


@pytest.fixture
def folder(tmp_path):
    (tmp_path / "graphs.md").write_text("# Graph algorithms\nDijkstra finds the shortest path in a weighted graph.")
    (tmp_path / "heaps.txt").write_text("A heap is a priority queue. Dijkstra uses a heap.")
    old = tmp_path / "old.txt"
    old.write_text("dijkstra was a Dutch computer scientist")
    os.utime(old, (1_000_000, 1_000_000))                      # make this note clearly the oldest
    return tmp_path


@pytest.fixture
def client(folder):
    nb = Notebook(folder)
    nb.sync()
    return create_app(nb).test_client()


def test_home_page_and_static_assets(client):
    home = client.get("/")
    assert home.status_code == 200 and b"NoteSearch" in home.data and b"/static/js/app.js" in home.data
    for path, kind in [("/static/css/style.css", b"--accent"), ("/static/js/app.js", b"import"),
                       ("/static/favicon.svg", b"<svg")]:
        r = client.get(path)
        assert r.status_code == 200 and kind in r.data, path


def test_search_returns_ranked_results(client):
    data = client.get("/api/search?q=dijkstra").get_json()
    assert {x["path"] for x in data["results"]} == {"graphs.md", "heaps.txt", "old.txt"}
    top = data["results"][0]
    assert top["relative"] == 1.0 and "<mark>" in top["snippet"]
    assert {"type", "modified", "words", "score"} <= set(top) and "took_ms" in data


def test_search_options(client):
    assert client.get("/api/search?q=grahp").get_json()["results"]                 # typo fixed
    assert not client.get("/api/search?q=grahp&fuzzy=0").get_json()["results"]     # typo fixing off
    assert not client.get("/api/search?q=heap+graph").get_json()["results"]        # AND
    assert len(client.get("/api/search?q=heap+graph&any=1").get_json()["results"]) == 2
    assert len(client.get("/api/search?q=dijkstra&k=1").get_json()["results"]) == 1
    assert client.get("/api/search?q=").get_json()["results"] == []


def test_search_file_type_filter(client):
    md = client.get("/api/search?q=dijkstra&types=md").get_json()["results"]
    assert [r["path"] for r in md] == ["graphs.md"] and md[0]["type"] == "md"
    both = client.get("/api/search?q=dijkstra&types=md,txt").get_json()["results"]
    assert len(both) == 3
    assert client.get("/api/search?q=dijkstra&types=pdf").get_json()["results"] == []


def test_search_sort_newest(client):
    by_score = [r["path"] for r in client.get("/api/search?q=dijkstra").get_json()["results"]]
    newest = [r["path"] for r in client.get("/api/search?q=dijkstra&sort=newest").get_json()["results"]]
    assert sorted(by_score) == sorted(newest) and newest[-1] == "old.txt"


def test_doc_view_highlights_whole_note(client):
    d = client.get("/api/doc?path=graphs.md&q=dijkstra").get_json()
    assert d["title"] == "Graph algorithms" and d["matches"] == 1 and d["type"] == "md"
    assert "<mark>Dijkstra</mark>" in d["html"]
    plain = client.get("/api/doc?path=graphs.md").get_json()
    assert plain["matches"] == 0 and "<mark>" not in plain["html"]


def test_doc_unknown_or_traversal_path_is_404(client):
    assert client.get("/api/doc?path=nope.md").status_code == 404
    assert client.get("/api/doc?path=../../etc/passwd").status_code == 404


def test_doc_escapes_html(tmp_path):
    (tmp_path / "x.txt").write_text("<script>alert(1)</script> hello")
    nb = Notebook(tmp_path); nb.sync()
    d = create_app(nb).test_client().get("/api/doc?path=x.txt&q=hello").get_json()
    assert "<script>" not in d["html"] and "&lt;script&gt;" in d["html"]


def test_notes_list(client):
    notes = client.get("/api/notes").get_json()["notes"]
    assert [n["title"] for n in notes] == ["Graph algorithms", "heaps", "old"]
    assert {n["type"] for n in notes} == {"md", "txt"}


def test_overview_dashboard(client):
    o = client.get("/api/overview").get_json()
    assert o["notes"] == 3 and o["types"] == {"md": 1, "txt": 2}
    assert o["unique_words"] > 10 and o["total_words"] > 20
    words = [w["word"] for w in o["top_words"]]
    assert "dijkstra" in words and "the" not in words and "a" not in words      # stop words hidden
    assert o["top_words"][0]["count"] >= o["top_words"][-1]["count"]
    assert o["recent"][0]["path"] != "old.txt" and len(o["recent"]) == 3
    assert client.get("/api/stats").get_json()["notes"] == 3


def test_reindex_picks_up_new_note(client, folder):
    (folder / "new.md").write_text("trie notes")
    s = client.post("/api/reindex").get_json()
    assert s["added"] == 1
    assert client.get("/api/search?q=trie").get_json()["results"]
    assert client.get("/api/reindex").status_code == 405                          # POST only
