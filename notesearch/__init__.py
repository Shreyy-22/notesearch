"""notesearch: a small full-text search engine for your own notes."""
from .notebook import Notebook
from .index import SearchIndex

__all__ = ["Notebook", "SearchIndex"]
