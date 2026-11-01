"""Parse a search string.

  graph "shortest path" -weighted -"dead end"
    -> terms=[graph]  phrases=[[shortest, path]]  not_terms=[weighted]  not_phrases=[[dead, end]]
"""
import re
from dataclasses import dataclass, field

from .tokenizer import terms as tokenize_terms

_PART = re.compile(r'(-?)"([^"]*)"|(-?)([^\s"]+)')


@dataclass
class Query:
    terms: list[str] = field(default_factory=list)
    phrases: list[list[str]] = field(default_factory=list)
    not_terms: list[str] = field(default_factory=list)
    not_phrases: list[list[str]] = field(default_factory=list)


def parse_query(text: str) -> Query:
    q = Query()
    for m in _PART.finditer(text):
        neg = (m.group(1) or m.group(3)) == "-"
        toks = tokenize_terms(m.group(2) if m.group(2) is not None else m.group(4))
        if not toks:
            continue
        if len(toks) == 1:  # "word" or a bare word
            (q.not_terms if neg else q.terms).append(toks[0])
        else:  # quoted phrase, or something like well-known / don't
            (q.not_phrases if neg else q.phrases).append(toks)
    return q
