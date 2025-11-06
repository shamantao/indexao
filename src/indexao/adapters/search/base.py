"""
Search adapter interface.

Defines the protocol for search backends to index and search documents.
"""

from dataclasses import dataclass, field
from typing import Protocol, List, Optional, Dict, Any, runtime_checkable
from datetime import datetime
from pathlib import Path


@dataclass
class IndexedDocument:
    """
    Document to be indexed.
    
    Attributes:
        doc_id: Unique document identifier
        title: Document title
        content: Document text content
        language: Document language code
        file_path: Path to original file
        metadata: Additional metadata (author, date, tags, etc.)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    doc_id: str
    title: str
    content: str
    language: str
    file_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __repr__(self) -> str:
        """String representation."""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (
            f"IndexedDocument(id={self.doc_id}, "
            f"title='{self.title}', "
            f"lang={self.language}, "
            f"content='{content_preview}')"
        )


@dataclass
class SearchResult:
    """
    Search result entry.
    
    Attributes:
        doc_id: Document identifier
        title: Document title
        content_snippet: Excerpt from content (with highlight context)
        score: Relevance score (0.0-1.0, higher = more relevant)
        language: Document language code
        metadata: Additional metadata
        highlights: List of matched terms/phrases
    """
    doc_id: str
    title: str
    content_snippet: str
    score: float
    language: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    highlights: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate score range."""
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")
    
    def __repr__(self) -> str:
        """String representation."""
        snippet_preview = self.content_snippet[:50] + "..." if len(self.content_snippet) > 50 else self.content_snippet
        return (
            f"SearchResult(id={self.doc_id}, "
            f"title='{self.title}', "
            f"score={self.score:.2f}, "
            f"snippet='{snippet_preview}')"
        )


@runtime_checkable
class SearchAdapter(Protocol):
    """
    Protocol for search adapters.
    
    All search backends must implement this interface.
    """
    
    @property
    def name(self) -> str:
        """
        Name of the search backend.
        
        Returns:
            Backend name (e.g., 'meilisearch', 'tantivy', 'sqlite-fts')
        """
        ...
    
    def index_document(self, document: IndexedDocument) -> bool:
        """
        Index a single document.
        
        Args:
            document: Document to index
        
        Returns:
            True if indexed successfully, False otherwise
        
        Raises:
            RuntimeError: If indexing fails
        
        Example:
            >>> adapter = MeilisearchAdapter()
            >>> doc = IndexedDocument(
            ...     doc_id="123",
            ...     title="Sample Doc",
            ...     content="This is a test document",
            ...     language="en"
            ... )
            >>> adapter.index_document(doc)
        """
        ...
    
    def index_batch(self, documents: List[IndexedDocument]) -> int:
        """
        Index multiple documents (batch operation).
        
        Args:
            documents: List of documents to index
        
        Returns:
            Number of documents successfully indexed
        
        Note:
            More efficient than indexing documents one by one.
        """
        ...
    
    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        language: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for documents matching query.
        
        Args:
            query: Search query text
            limit: Maximum number of results to return
            offset: Number of results to skip (pagination)
            language: Filter by language (None = all languages)
            filters: Additional filters (e.g., {'author': 'John'})
        
        Returns:
            List of SearchResult objects, sorted by relevance (descending)
        
        Example:
            >>> adapter = MeilisearchAdapter()
            >>> results = adapter.search("Python programming", limit=5)
            >>> for result in results:
            ...     print(f"{result.title}: {result.score}")
        """
        ...
    
    def get_document(self, doc_id: str) -> Optional[IndexedDocument]:
        """
        Retrieve a document by ID.
        
        Args:
            doc_id: Document identifier
        
        Returns:
            IndexedDocument if found, None otherwise
        """
        ...
    
    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update document fields.
        
        Args:
            doc_id: Document identifier
            updates: Fields to update (e.g., {'title': 'New Title'})
        
        Returns:
            True if updated successfully, False otherwise
        """
        ...
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from index.
        
        Args:
            doc_id: Document identifier
        
        Returns:
            True if deleted successfully, False otherwise
        """
        ...
    
    def count_documents(self, language: Optional[str] = None) -> int:
        """
        Count indexed documents.
        
        Args:
            language: Filter by language (None = all languages)
        
        Returns:
            Number of documents in index
        """
        ...
    
    def clear_index(self) -> bool:
        """
        Clear all documents from index.
        
        Returns:
            True if cleared successfully, False otherwise
        
        Warning:
            This operation is irreversible!
        """
        ...
    
    def is_available(self) -> bool:
        """
        Check if search backend is available.
        
        Returns:
            True if backend is ready to use, False otherwise
        """
        ...
    
    def get_version(self) -> str:
        """
        Get search backend version.
        
        Returns:
            Version string
        """
        ...
