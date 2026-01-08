"""
Cloud Storage Indexer
Manages progressive indexing of cloud storage volumes.
"""

import os
import time
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import httpx

from indexao.logger import get_logger
from indexao.scanner import scan_directory
from indexao.database import DocumentDatabase
from indexao.processor import DocumentProcessor
from indexao.config import get_config

logger = get_logger(__name__)


@dataclass
class CloudVolume:
    """Configuration for a cloud storage volume."""
    name: str
    mount_path: str
    index_name: str
    file_patterns: List[str]
    exclude_patterns: List[str]
    enabled: bool = True
    last_scan: Optional[str] = None
    total_files: int = 0
    indexed_files: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CloudVolume':
        return cls(**data)


class CloudIndexerState:
    """Persistent state for cloud indexing."""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.volumes: Dict[str, CloudVolume] = {}
        self.load()
    
    def load(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.volumes = {
                        name: CloudVolume.from_dict(vol_data)
                        for name, vol_data in data.get('volumes', {}).items()
                    }
                logger.info(f"Loaded state for {len(self.volumes)} cloud volumes")
            except Exception as e:
                logger.error(f"Error loading state: {e}")
    
    def save(self):
        """Save state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump({
                    'volumes': {
                        name: vol.to_dict()
                        for name, vol in self.volumes.items()
                    },
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
            logger.debug(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def update_volume(self, volume: CloudVolume):
        """Update volume in state."""
        # Reload state to avoid overwriting external changes (e.g. deletions from UI)
        self.load()
        self.volumes[volume.name] = volume
        self.save()


class CloudIndexer:
    """
    Progressive cloud storage indexer.
    
    Features:
    - Detects when volumes are mounted
    - Progressive indexing in batches
    - Resumable (tracks progress)
    - Multi-cloud support with separate indexes
    """
    
    def __init__(
        self,
        state_file: Optional[Path] = None,
        batch_size: int = 100,
        check_interval: int = 60,
        meilisearch_url: str = "http://localhost:7700"
    ):
        from indexao.config import get_config
        try:
            config = get_config()
            self.db_path = config.db_path
            self.throttle_path = config.throttle_config_path
            if state_file is None:
                state_file = config.db_path.parent / "cloud_indexer_state.json"
        except RuntimeError:
             # Fallback if config not loaded yet (should not happen in normal run)
             self.db_path = Path("data/db/indexao.db")
             self.throttle_path = Path("data/db/throttling.json")
             if state_file is None:
                 state_file = Path("data/db/cloud_indexer_state.json")

        self.state = CloudIndexerState(state_file)
        self.batch_size = batch_size
        self.check_interval = check_interval
        self.meilisearch_url = meilisearch_url
        from indexao.database import DocumentDatabase
        self.db = DocumentDatabase(str(self.db_path))
        self.processor = None
        # Throttling config
        self.throttle = self._load_throttle_config()
        logger.info(f"CloudIndexer initialized: Meilisearch at {meilisearch_url}")

    def _load_throttle_config(self) -> Dict[str, int]:
        cfg_path = self.throttle_path
        if cfg_path.exists():
            try:
                with open(cfg_path) as f:
                    data = json.load(f)
                return {
                    'batch_size': data.get('batch_size', self.batch_size),
                    'sleep_ms': data.get('sleep_ms', 1000),
                    'max_docs_per_minute': data.get('max_docs_per_minute', 5000)
                }
            except Exception as e:
                logger.error(f"Failed loading throttle config: {e}")
        # Defaults
        return {'batch_size': self.batch_size, 'sleep_ms': 1000, 'max_docs_per_minute': 5000}

    def _save_throttle_config(self):
        cfg_path = self.throttle_path
        try:
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cfg_path, 'w') as f:
                json.dump(self.throttle, f, indent=2)
            logger.info("✓ Throttle config saved")
        except Exception as e:
            logger.error(f"Failed saving throttle config: {e}")
        
    async def ensure_index_exists(self, index_name: str) -> bool:
        """Ensure that a Meilisearch index exists, create it if not."""
        try:
            async with httpx.AsyncClient() as client:
                # Check if index exists
                response = await client.get(f"{self.meilisearch_url}/indexes/{index_name}")
                
                if response.status_code == 200:
                    logger.debug(f"Index {index_name} already exists")
                    return True
                
                # Create index
                logger.info(f"Creating index: {index_name}")
                response = await client.post(
                    f"{self.meilisearch_url}/indexes",
                    json={"uid": index_name, "primaryKey": "id"}
                )
                
                if response.status_code in (200, 201, 202):
                    logger.info(f"✓ Index {index_name} created successfully")
                    return True
                else:
                    logger.error(f"Failed to create index {index_name}: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error ensuring index {index_name} exists: {e}")
            return False
        
    def add_volume(
        self,
        name: str,
        mount_path: str,
        index_name: str,
        file_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> CloudVolume:
        """Add a cloud volume to track."""
        # Check if volume already exists - preserve its state
        if name in self.state.volumes:
            existing = self.state.volumes[name]
            logger.debug(f"Volume {name} already exists, preserving state (total={existing.total_files}, indexed={existing.indexed_files})")
            # Update paths/patterns if needed, but keep progress
            existing.mount_path = mount_path
            existing.index_name = index_name
            if file_patterns:
                existing.file_patterns = file_patterns
            if exclude_patterns:
                existing.exclude_patterns = exclude_patterns
            # No need to save - state unchanged except paths
            return existing
        
        # New volume - create with defaults
        if file_patterns is None:
            file_patterns = ['*.pdf', '*.txt', '*.doc', '*.docx', '*.png', '*.jpg', '*.jpeg']
        
        if exclude_patterns is None:
            exclude_patterns = [
                '*/.*',  # Hidden files
                '*/.git/*',
                '*/node_modules/*',
                '*/__pycache__/*',
                '*/venv/*',
                '*.tmp',
                '*.cache'
            ]
        
        volume = CloudVolume(
            name=name,
            mount_path=mount_path,
            index_name=index_name,
            file_patterns=file_patterns,
            exclude_patterns=exclude_patterns
        )
        
        self.state.update_volume(volume)
        logger.info(f"Added cloud volume: {name} -> {mount_path}")
        return volume
    
    def is_mounted(self, volume: CloudVolume) -> bool:
        """Check if volume is currently mounted."""
        path = Path(volume.mount_path)
        return path.exists() and path.is_dir()
    
    def get_mounted_volumes(self) -> List[CloudVolume]:
        """Get list of currently mounted volumes."""
        return [
            vol for vol in self.state.volumes.values()
            if vol.enabled and self.is_mounted(vol)
        ]
    
    def scan_volume(self, volume: CloudVolume) -> List[Path]:
        """Scan volume for indexable files."""
        logger.info(f"Scanning volume: {volume.name} ({volume.mount_path})")
        
        try:
            from indexao.scanner import FileScanner
            
            # Get extensions from patterns (*.pdf -> .pdf)
            extensions = set()
            for pattern in volume.file_patterns:
                if pattern.startswith('*.'):
                    extensions.add(pattern[1:])  # Remove *
            
            scanner = FileScanner(
                root_dir=volume.mount_path,
                recursive=True,
                include_hidden=False,
                allowed_extensions=extensions if extensions else None
            )
            
            file_metadata_list = scanner.scan()
            
            file_metadata_list = scanner.scan()
            files = [fm.path for fm in file_metadata_list]
            
            # Apply exclude patterns
            filtered_files = []
            for file_path in files:
                # Check if file matches any exclude pattern
                should_exclude = False
                for pattern in volume.exclude_patterns:
                    import fnmatch
                    if fnmatch.fnmatch(str(file_path), pattern):
                        should_exclude = True
                        break
                
                if not should_exclude:
                    filtered_files.append(file_path)
            
            logger.info(f"Found {len(filtered_files)} files (filtered from {len(files)})")
            volume.total_files = len(filtered_files)
            self.state.update_volume(volume)
            
            # Populate persistent queue
            for file_path in filtered_files:
                try:
                    stat = file_path.stat()
                    self.db.index_queue_add(
                        volume=volume.name,
                        path=str(file_path),
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                    )
                except Exception as e:
                    logger.error(f"Queue add failed for {file_path}: {e}")

            logger.info(f"Queued {len(filtered_files)} files for volume {volume.name}")
            return filtered_files
            
        except Exception as e:
            logger.error(f"Error scanning volume {volume.name}: {e}")
            return []

    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return ""

    def _check_db_for_hash(self, file_hash: str) -> Optional[str]:
        """Check if hash exists in documents table."""
        try:
            with self.db._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT doc_id FROM documents WHERE file_hash = ?", (file_hash,))
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception:
            pass
        return None

    def _prepare_docs(self, volume: CloudVolume, queue_rows: List) -> List[Dict]:
        documents = []
        for row in queue_rows:
            file_path = Path(row['path'])
            try:
                # 1. Compute Content Hash (Sprint 2: CAS Strategy)
                content_hash = self._compute_sha256(file_path)
                
                # Default ID logic (fallback)
                doc_id = f"{volume.name}_{abs(hash(str(file_path)))}" 
                
                # 2. Check for "Rendez-vous" (Fast-Track Convergence)
                existing_doc_id = self._check_db_for_hash(content_hash) if content_hash else None
                
                if existing_doc_id:
                    logger.info(f"Rendez-vous! File {file_path.name} matches existing doc {existing_doc_id}")
                    doc_id = existing_doc_id
                    # We reuse the existing ID, Meilisearch will merge/update metadata
                elif content_hash:
                     # New document, use Hash-based ID for future convergence
                     doc_id = f"HASH_{content_hash}"

                doc = {
                    "id": doc_id,
                    "volume": volume.name,
                    "filename": file_path.name,
                    "path": str(file_path),
                    "extension": file_path.suffix.lower(),
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat() if file_path.exists() else None,
                    "indexed_at": datetime.now().isoformat(),
                    "file_hash": content_hash # Store hash in Meilisearch too
                }
                documents.append(doc)
            except Exception as e:
                logger.error(f"Error preparing {file_path}: {e}")
        return documents

    def process_queue_batch(self, volume: CloudVolume) -> int:
        """Process one batch from persistent queue with throttling."""
        batch_size = self.throttle.get('batch_size', self.batch_size)
        rows = self.db.index_queue_get_batch(volume.name, batch_size)
        if not rows:
            return 0
        ids = [r['id'] for r in rows]
        self.db.index_queue_mark_processing(ids)
        documents = self._prepare_docs(volume, rows)
        if not documents:
            self.db.index_queue_mark_error(ids, 'prepare_failed')
            return 0
        ok = self.send_to_meilisearch_sync(volume.index_name, documents)
        if ok:
            self.db.index_queue_mark_done(ids)
            volume.indexed_files = min(volume.indexed_files + len(documents), volume.total_files)
            volume.last_scan = datetime.now().isoformat()
            self.state.update_volume(volume)
            return len(documents)
        else:
            self.db.index_queue_mark_error(ids, 'send_failed')
            return 0
    
    async def _send_to_meilisearch(self, index_name: str, documents: List[Dict]) -> bool:
        """[Deprecated in async context] Use sync variant to avoid asyncio.run issues."""
        try:
            await self.ensure_index_exists(index_name)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.meilisearch_url}/indexes/{index_name}/documents",
                    json=documents
                )
                return response.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"Error (async) sending to Meilisearch: {e}")
            return False

    def ensure_index_exists_sync(self, index_name: str) -> bool:
        """Ensure that a Meilisearch index exists (sync version)."""
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(f"{self.meilisearch_url}/indexes/{index_name}")
                if resp.status_code == 200:
                    return True
                resp = client.post(
                    f"{self.meilisearch_url}/indexes",
                    json={"uid": index_name, "primaryKey": "id"}
                )
                return resp.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"Error ensuring index (sync) {index_name}: {e}")
            return False

    def send_to_meilisearch_sync(self, index_name: str, documents: List[Dict]) -> bool:
        """Send documents synchronously to Meilisearch and verify task completion."""
        try:
            if not self.ensure_index_exists_sync(index_name):
                logger.error(f"Cannot ensure index exists: {index_name}")
                return False
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.meilisearch_url}/indexes/{index_name}/documents",
                    json=documents
                )
                
                if response.status_code not in (200, 201, 202):
                    logger.error(f"Meilisearch error: {response.status_code} - {response.text}")
                    return False
                
                # Get task UID to check status
                task_data = response.json()
                task_uid = task_data.get("taskUid")
                
                if not task_uid:
                    logger.warning(f"No taskUid returned, assuming success for {len(documents)} docs")
                    return True
                
                # Wait for task completion (with timeout)
                import time
                max_wait = 10  # seconds
                start = time.time()
                
                while time.time() - start < max_wait:
                    task_resp = client.get(f"{self.meilisearch_url}/tasks/{task_uid}")
                    if task_resp.status_code == 200:
                        task_info = task_resp.json()
                        status = task_info.get("status")
                        
                        if status == "succeeded":
                            logger.debug(f"Successfully indexed {len(documents)} documents")
                            return True
                        elif status == "failed":
                            error = task_info.get("error", {})
                            logger.error(f"Meilisearch task failed: {error.get('message', 'Unknown error')}")
                            logger.error(f"First failing doc ID: {documents[0].get('id') if documents else 'N/A'}")
                            return False
                        elif status in ("enqueued", "processing"):
                            time.sleep(0.5)
                            continue
                    time.sleep(0.5)
                
                # Timeout - assume success but log warning
                logger.warning(f"Task {task_uid} timeout after {max_wait}s, assuming success")
                return True
                
        except Exception as e:
            logger.error(f"Error sending to Meilisearch (sync): {e}")
            return False
    
    def index_volume_progressive(self, volume: CloudVolume) -> Dict[str, Any]:
        """
        Progressively index a volume.
        Returns indexing statistics.
        """
        if not self.is_mounted(volume):
            logger.warning(f"Volume {volume.name} is not mounted")
            return {
                'status': 'error',
                'message': 'Volume not mounted'
            }
        
        # Scan for files
        files = self.scan_volume(volume)
        
        if not files:
            logger.info(f"No files to index in {volume.name}")
            return {
                'status': 'success',
                'files_indexed': 0,
                'total_files': 0
            }
        
        # Process queue based on throttling
        total_indexed = 0
        docs_per_minute = 0
        window_start = time.time()
        max_per_minute = self.throttle.get('max_docs_per_minute', 5000)
        sleep_ms = self.throttle.get('sleep_ms', 1000)
        while True:
            # Rate limit per minute
            now = time.time()
            if now - window_start >= 60:
                window_start = now
                docs_per_minute = 0
            if docs_per_minute >= max_per_minute:
                logger.info("Throttling: max docs per minute reached, sleeping")
                time.sleep(5)
                continue
            count = self.process_queue_batch(volume)
            if count == 0:
                break
            docs_per_minute += count
            total_indexed += count
            logger.info(f"Progress queue: {total_indexed}/{volume.total_files} ({(total_indexed/volume.total_files*100) if volume.total_files else 0:.1f}%)")
            time.sleep(sleep_ms/1000.0)
        
        logger.info(f"✓ Completed indexing {volume.name}: {total_indexed} files")
        
        return {
            'status': 'success',
            'volume': volume.name,
            'files_indexed': total_indexed,
            'total_files': volume.total_files
        }
    
    def run_daemon(self):
        """
        Run as daemon: monitor and index mounted volumes.
        """
        logger.info("Starting Cloud Indexer daemon")
        logger.info(f"Monitoring {len(self.state.volumes)} volumes")
        logger.info(f"Check interval: {self.check_interval}s")
        
        try:
            while True:
                # Reload state to catch configuration changes
                self.state.load()
                
                mounted = self.get_mounted_volumes()
                
                if mounted:
                    logger.info(f"Found {len(mounted)} mounted volumes")
                    
                    for volume in mounted:
                        # Check if indexing is needed
                        if volume.indexed_files < volume.total_files or volume.last_scan is None:
                            logger.info(f"Indexing {volume.name}...")
                            result = self.index_volume_progressive(volume)
                            logger.info(f"Result: {result}")
                
                else:
                    logger.debug("No mounted volumes found")
                
                # Wait before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("Cloud Indexer daemon stopped")


def setup_default_volumes() -> CloudIndexer:
    """
    Initialize CloudIndexer. 
    Does NOT add default volumes anymore (user must configure them via UI).
    """
    return CloudIndexer()



if __name__ == "__main__":
    # CLI usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Cloud Storage Indexer")
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--scan', type=str, help='Scan specific volume')
    parser.add_argument('--list', action='store_true', help='List configured volumes')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for indexing')
    
    args = parser.parse_args()
    
    indexer = setup_default_volumes()
    
    if args.list:
        print("\n📁 Configured Cloud Volumes:")
        for name, vol in indexer.state.volumes.items():
            mounted = "✓ mounted" if indexer.is_mounted(vol) else "✗ not mounted"
            progress = f"{vol.indexed_files}/{vol.total_files}" if vol.total_files > 0 else "not scanned"
            print(f"  {name}: {vol.mount_path} ({mounted}) - {progress}")
    
    elif args.scan:
        vol = indexer.state.volumes.get(args.scan)
        if vol:
            result = indexer.index_volume_progressive(vol)
            print(f"\n✓ Indexing result: {result}")
        else:
            print(f"❌ Volume '{args.scan}' not found")
    
    elif args.daemon:
        indexer.batch_size = args.batch_size
        indexer.run_daemon()
    
    else:
        parser.print_help()
