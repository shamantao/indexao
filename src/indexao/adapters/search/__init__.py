"""Search adapter module."""

from indexao.adapters.search.base import SearchAdapter, SearchResult, IndexedDocument
from indexao.adapters.search.mock import MockSearchAdapter
from indexao.adapters.search.meilisearch import MeilisearchAdapter

__all__ = ['SearchAdapter', 'SearchResult', 'IndexedDocument', 'MockSearchAdapter', 'MeilisearchAdapter']
