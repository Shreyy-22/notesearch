"""BK-tree for typo-tolerant lookup.

DSA: a metric tree. Every edge is labelled with the edit distance between parent
and child. Because edit distance obeys the triangle inequality, a search for
"words within distance d of X" only has to follow edges labelled in
[dist(X, node) - d, dist(X, node) + d] and can skip the rest of the tree.
"""


def levenshtein(a: str, b: str) -> int:
    """Edit distance with two rolling rows: O(len(a) * len(b)) time, O(len(b)) space."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class BKTree:
    def __init__(self):
        self.root: tuple[str, dict] | None = None  # (word, {distance: child})
        self.size = 0

    def add(self, word: str) -> None:
        if self.root is None:
            self.root, self.size = (word, {}), 1
            return
        node = self.root
        while True:
            w, kids = node
            d = levenshtein(word, w)
            if d == 0:
                return
            if d in kids:
                node = kids[d]
            else:
                kids[d] = (word, {})
                self.size += 1
                return

    def search(self, word: str, max_dist: int) -> list[tuple[str, int]]:
        """All stored words within `max_dist` edits, closest first."""
        if self.root is None:
            return []
        out, stack = [], [self.root]
        while stack:
            w, kids = stack.pop()
            d = levenshtein(word, w)
            if d <= max_dist:
                out.append((w, d))
            for edge, child in kids.items():
                if d - max_dist <= edge <= d + max_dist:
                    stack.append(child)
        return sorted(out, key=lambda x: (x[1], x[0]))
