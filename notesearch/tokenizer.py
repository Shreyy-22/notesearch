"""Turn text into lowercase tokens, remembering where each one sits in the text."""
import re

_WORD = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[tuple[str, int, int]]:
    """Return (token, start_char, end_char) for every word in `text`."""
    return [(m.group().lower(), m.start(), m.end()) for m in _WORD.finditer(text)]


def terms(text: str) -> list[str]:
    return [t for t, _, _ in tokenize(text)]
