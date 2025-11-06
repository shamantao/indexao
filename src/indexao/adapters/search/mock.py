"""Mock search adapter for testing."""

from typing import List, Optional, Dict, Any
from datetime import datetime

from indexao.adapters.search.base import SearchAdapter, SearchResult, IndexedDocument
from indexao.logger import get_logger

logger = get_logger(__name__)


class MockSearchAdapter:
    """
    Mock search backend that stores documents in memory.
    
    Useful for testing without requiring actual search engine installation.
    """
    
    def __init__(self):
        """Initialize mock search backend."""
        self._documents: Dict[str, IndexedDocument] = {}
        logger.debug("Initialized MockSearchAdapter with in-memory storage")
    
    @property
    def name(self) -> str:
        """Backend name."""
        return "mock-search"
    
    def index_document(self, document: IndexedDocument) -> bool:
        """Index a document."""
        logger.debug(f"Mock indexing document: {document.doc_id}")
        self._documents[document.doc_id] = document
        return True
    
    def index_batch(self, documents: List[IndexedDocument]) -> int:
        """Index multiple documents."""
        count = 0
        for doc in documents:
            if self.index_document(doc):
                count += 1
        logger.info(f"Mock indexed {count}/{len(documents)} documents")
        return count
    
    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        language: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for documents (simple substring match).
        
        Args:
            query: Search query
            limit: Max results
            offset: Skip results
            language: Filter by language
            filters: Additional filters
        
        Returns:
            List of SearchResult objects
        """
        logger.debug(f"Mock searching for: '{query}' (limit={limit}, offset={offset})")
        
        results = []
        query_lower = query.lower()
        
        for doc in self._documents.values():
            # Language filter
            if language and doc.language != language:
                continue
            
            # Simple substring match
            if query_lower in doc.title.lower() or query_lower in doc.content.lower():
                # Calculate mock score (higher if in title)
                score = 1.0 if query_lower in doc.title.lower() else 0.5
                
                # Extract snippet around match
                content_lower = doc.content.lower()
                match_pos = content_lower.find(query_lower)
                if match_pos >= 0:
                    start = max(0, match_pos - 50)
                    end = min(len(doc.content), match_pos + 100)
                    snippet = doc.content[start:end]
                else:
                    snippet = doc.content[:150]
                
                results.append(SearchResult(
                    doc_id=doc.doc_id,
                    title=doc.title,
                    content_snippet=snippet,
                    score=score,
                    language=doc.language,
                    metadata=doc.metadata,
                    highlights=[query]
                ))
        
        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)
        
        # Apply pagination
        results = results[offset:offset + limit]
        
        logger.debug(f"Mock search found {len(results)} results")
        return results
    
    def get_document(self, doc_id: str) -> Optional[IndexedDocument]:
        """Retrieve document by ID."""
        return self._documents.get(doc_id)
    
    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """Update document fields."""
        doc = self._documents.get(doc_id)
        if not doc:
            return False
        
        # Update fields
        for key, value in updates.items():
            if hasattr(doc, key):
                setattr(doc, key, value)
        
        doc.updated_at = datetime.now()
        logger.debug(f"Mock updated document: {doc_id}")
        return True
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            logger.debug(f"Mock deleted document: {doc_id}")
            return True
        return False
    
    def count_documents(self, language: Optional[str] = None) -> int:
        """Count documents."""
        if language:
            return sum(1 for doc in self._documents.values() if doc.language == language)
        return len(self._documents)
    
    def clear_index(self) -> bool:
        """Clear all documents."""
        count = len(self._documents)
        self._documents.clear()
        logger.info(f"Mock cleared {count} documents")
        return True
    
    def is_available(self) -> bool:
        """Always available."""
        return True
    
    def get_version(self) -> str:
        """Mock version."""
        return "1.0.0-mock"
