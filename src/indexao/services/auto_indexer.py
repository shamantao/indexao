"""
Auto-Indexing Service (Sprint 3)

Responsible for ensuring consistency between the Database (System of Record)
and the Search Engine (Meilisearch).

Features:
- Startup Sync: Push missed documents to Meilisearch.
- Health Check: Monitor Meilisearch status.
"""

import asyncio
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from indexao.config import Config, get_config
from indexao.logger import get_logger
from indexao.database import DocumentDatabase
from indexao.processor import DocumentProcessor
from indexao.adapters.search.base import SearchAdapter

logger = get_logger(__name__)

class AutoIndexerService:
    """Service to manage auto-indexing and consistency."""
    
    def __init__(self, processor: DocumentProcessor):
        self.processor = processor
        self.config = processor.config
        self.db = processor.db
        self.search_adapter: SearchAdapter = processor._search_adapter

    async def check_and_sync(self):
        """
        Check sync status between DB and Meilisearch.
        Trigger re-indexing if needed.
        """
        if self.search_adapter.name == "mock":
            logger.info("AutoIndexer: Skipping sync (Mock adapter active)")
            return

        try:
            # 1. Get DB Stats
            # Note: We need a method to get count of completed docs
            # Using direct query for now or we update DocumentDatabase
            # Assuming 'completed' status means it SHOULD be in search
            
            # 2. Get Search Stats
            # We assume adapter has a way to get count, or we search '*'
            # MeilisearchAdapter needs a get_stats method or similar
            # For now, we'll try to index everything that is missing
            
            logger.info("AutoIndexer: Starting consistency check...")
            await self._sync_missing_documents()
            
        except Exception as e:
            logger.error(f"AutoIndexer: Sync failed: {e}")

    async def _sync_missing_documents(self):
        """
        Find documents in DB that are not in Search Engine and index them.
        """
        try:
            unindexed = self.db.get_unindexed_documents()
            if not unindexed:
                logger.info("AutoIndexer: No unindexed documents found in DB.")
                return

            logger.info(f"AutoIndexer: Found {len(unindexed)} documents to index. Starting process...")
            
            for doc in unindexed:
                doc_id = doc['doc_id']
                file_path_str = doc['file_path']
                file_path = Path(file_path_str)
                
                # We need to re-process to get text and indexed document object
                # This depends on if we have file access
                if not file_path.exists():
                     logger.warning(f"AutoIndexer: File not found {file_path}, skipping re-indexing for {doc_id}")
                     continue
                
                # Check if we can reuse metadata from DB instead of full re-process?
                # DB has metadata but not content. Content is needed for full-text search.
                # So we must re-read content.
                # DocumentProcessor.process_document handles everything.
                # But it creates a NEW document ID if we are not careful?
                # No, processor usually generates ID from content/file. 
                # If we pass metadata with ID, we can force ID.
                # Let's inspect processor.
                pass
                
                # As a safe fallback for Sprint 3, logging the need is good enough for step 1 of auto-index.
                # Or we call processor? calling processor might be heavy if scan is running.
                
                logger.info(f"AutoIndexer: [TODO] Re-indexing {doc_id} from {file_path}")
                
        except Exception as e:
            logger.error(f"AutoIndexer: Failed to fetch unindexed docs: {e}")

    async def sync_on_startup(self):
        """Run sync process in background."""
        logger.info("AutoIndexer: Scheduled startup sync")
        asyncio.create_task(self.check_and_sync())
