"""Trie (prefix tree) used for autocomplete.

DSA: tree traversal + top-k selection.
  insert:   O(len(word))
  complete: O(len(prefix) + size of the subtree under the prefix)
"""
import heapq


class _Node:
    __slots__ = ("children", "freq", "word")

    def __init__(self):
        self.children: dict[str, "_Node"] = {}
        self.freq = 0
        self.word: str | None = None  # set only where a word ends


class Trie:
    def __init__(self):
        self.root = _Node()

    def insert(self, word: str, freq: int = 1) -> None:
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, _Node())
        node.word = word
        node.freq += freq

    def complete(self, prefix: str, k: int = 5) -> list[str]:
        """Up to k most frequent words starting with `prefix` (ties: alphabetical)."""
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return []
        found, stack = [], [node]  # iterative DFS: no recursion limit surprises
        while stack:
            n = stack.pop()
            if n.word is not None:
                found.append((n.freq, n.word))
            stack.extend(n.children.values())
        best = heapq.nsmallest(k, found, key=lambda fw: (-fw[0], fw[1]))
        return [w for _, w in best]
