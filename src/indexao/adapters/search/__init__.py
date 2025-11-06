"""Search adapter module."""

from indexao.adapters.search.base import SearchAdapter, SearchResult, IndexedDocument
from indexao.adapters.search.mock import MockSearchAdapter

__all__ = ['SearchAdapter', 'SearchResult', 'IndexedDocument', 'MockSearchAdapter']
