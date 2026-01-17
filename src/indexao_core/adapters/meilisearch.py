import meilisearch
from typing import List, Dict, Any
from indexao_core.config import MeiliConfig

class MeiliAdapter:
    def __init__(self, config: MeiliConfig):
        # If no key (dev mode), we might verify health first, but client allows None or empty string?
        # Ensure we pass None if empty or "masterKey" if that is what config has but server has none.
        # The logs said "The server will accept unidentified requests" if no master key.
        # But our config defaults to "masterKey". 
        # Ideally, we try to connect.
        self.client = meilisearch.Client(config.url, config.api_key if config.api_key else None)
        self.index_name = "documents"

    def ensure_index(self):
        """Create index and update settings."""
        try:
            self.client.get_index(self.index_name)
        except Exception:
            # meilisearch-python raises exception if not found
            self.client.create_index(self.index_name, {'primaryKey': 'id'})
        
        index = self.client.index(self.index_name)
        
        # Settings
        index.update_filterable_attributes([
            'language',
            'tags',
            'volume_path',
            'extension'
        ])
        
        # Searchable: Title, Translation, Content
        index.update_searchable_attributes([
            'original_filename',
            'translation',
            'content'
        ])

    def add_documents(self, documents: List[Dict[str, Any]]):
        """Add batch of documents."""
        if not documents:
            return
        index = self.client.index(self.index_name)
        # return task info
        return index.add_documents(documents)

    def clear_documents(self):
        """Remove all documents from the index."""
        index = self.client.index(self.index_name)
        return index.delete_all_documents()

    def health(self) -> Dict[str, Any]:
        return self.client.health()
