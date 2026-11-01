from __future__ import annotations

import argparse
import os
import sys
import time

from .highlight import make_snippet, render_ansi
from .notebook import Notebook, SyncStats, Watcher


def _fmt(s: SyncStats) -> str:
    msg = f"+{s.added} added, ~{s.updated} updated, -{s.removed} removed, {s.unchanged} unchanged"
    return msg + "".join(f"\n  ! {e}" for e in s.errors)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="notesearch", description="Search your notes.")
    p.add_argument("-d", "--dir", default=os.environ.get("NOTESEARCH_DIR", "."),
                   help="notes folder (default: $NOTESEARCH_DIR or current dir)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("index", help="scan the folder and update the saved index")

    s = sub.add_parser("search", help='search, e.g.  search "graph -weighted"')
    s.add_argument("query", nargs="+")
    s.add_argument("-k", type=int, default=10, help="max results")
    s.add_argument("--exact", action="store_true", help="turn off typo tolerance")
    s.add_argument("--prefix", action="store_true", help="treat the last word as a prefix")
    s.add_argument("--any", action="store_true", help="match ANY word instead of all")
    s.add_argument("--no-sync", action="store_true", help="skip the quick re-scan first")

    g = sub.add_parser("suggest", help="autocomplete the last word")
    g.add_argument("text", nargs="+")

    w = sub.add_parser("watch", help="keep the index fresh while you edit notes")
    w.add_argument("--interval", type=float, default=2.0)

    v = sub.add_parser("serve", help="small web UI")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8000)

    sub.add_parser("stats", help="index size info")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    nb = Notebook(args.dir)

    if args.cmd == "index":
        print(_fmt(nb.sync()))

    elif args.cmd == "search":
        if not args.no_sync:
            nb.sync()
        query = " ".join(args.query)
        hits = nb.search(query, k=args.k, fuzzy=not args.exact,
                         prefix=args.prefix, match_all=not args.any)
        if not hits:
            print("No results.")
            return 1
        color = sys.stdout.isatty()
        for i, h in enumerate(hits, 1):
            sn = make_snippet(h.doc, h.positions)
            body = render_ansi(sn) if color else sn.text
            print(f"{i:>2}. {h.doc.title}  [{h.score:.2f}]\n    {h.doc.path}\n    {body}\n")

    elif args.cmd == "suggest":
        nb.sync()
        for s in nb.suggest(" ".join(args.text)):
            print(s)

    elif args.cmd == "watch":
        print(f"Watching {nb.root}  (Ctrl+C to stop)")
        print(_fmt(nb.sync()))
        w = Watcher(nb, args.interval, on_change=lambda st: print(time.strftime("%H:%M:%S"), _fmt(st)))
        w.start()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            w.stop()

    elif args.cmd == "serve":
        from .web import create_app
        print(_fmt(nb.sync()))
        Watcher(nb, 2.0).start()
        print(f"Open http://{args.host}:{args.port}")
        create_app(nb).run(host=args.host, port=args.port, threaded=True)

    elif args.cmd == "stats":
        ix = nb.index
        size = nb.index_file.stat().st_size if nb.index_file.exists() else 0
        print(f"notes: {len(ix)}\nunique terms: {len(ix.postings)}\n"
              f"tokens: {ix.total_tokens}\nindex file: {size / 1024:.1f} KiB")
    return 0
