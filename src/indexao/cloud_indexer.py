"""
Cloud Storage Indexer
Manages progressive indexing of cloud storage volumes.
"""

import os
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

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
        state_file: Path = Path("data/cloud_indexer_state.json"),
        batch_size: int = 100,
        check_interval: int = 60
    ):
        self.state = CloudIndexerState(state_file)
        self.batch_size = batch_size
        self.check_interval = check_interval
        self.processor = None
        self.db = None
        
    def add_volume(
        self,
        name: str,
        mount_path: str,
        index_name: str,
        file_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> CloudVolume:
        """Add a cloud volume to track."""
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
            
            return filtered_files
            
        except Exception as e:
            logger.error(f"Error scanning volume {volume.name}: {e}")
            return []
    
    def index_batch(
        self,
        volume: CloudVolume,
        files: List[Path],
        start_idx: int = 0
    ) -> int:
        """
        Index a batch of files.
        Returns the number of files successfully indexed.
        """
        batch = files[start_idx:start_idx + self.batch_size]
        
        if not batch:
            return 0
        
        logger.info(f"Indexing batch {start_idx}-{start_idx + len(batch)} of {len(files)} files")
        
        indexed_count = 0
        
        for file_path in batch:
            try:
                # TODO: Add file to processing queue
                # For now, just log
                logger.debug(f"Queued: {file_path}")
                indexed_count += 1
                
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
        
        # Update progress
        volume.indexed_files = min(start_idx + indexed_count, volume.total_files)
        volume.last_scan = datetime.now().isoformat()
        self.state.update_volume(volume)
        
        return indexed_count
    
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
        
        # Start indexing from last position
        start_idx = volume.indexed_files
        total_indexed = 0
        
        while start_idx < len(files):
            batch_count = self.index_batch(volume, files, start_idx)
            total_indexed += batch_count
            start_idx += batch_count
            
            # Pause between batches to avoid overload
            if start_idx < len(files):
                logger.info(f"Progress: {start_idx}/{len(files)} ({start_idx/len(files)*100:.1f}%)")
                time.sleep(1)  # 1 second between batches
        
        logger.info(f"✓ Completed indexing {volume.name}: {total_indexed} files")
        
        return {
            'status': 'success',
            'volume': volume.name,
            'files_indexed': total_indexed,
            'total_files': len(files)
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
    """Setup default cloud volumes configuration."""
    indexer = CloudIndexer()
    
    # pCloud Drive (main cloud - 175k files)
    indexer.add_volume(
        name="pcloud_drive",
        mount_path="/Users/phil/pCloud Drive",
        index_name="pcloud_drive",
        file_patterns=[
            '*.pdf', '*.txt', '*.doc', '*.docx', '*.odt',
            '*.png', '*.jpg', '*.jpeg', '*.tiff',
            '*.md', '*.html', '*.json', '*.xml'
        ],
        exclude_patterns=[
            '*/.*',  # Hidden files/folders
            '*/.git/*',
            '*/node_modules/*',
            '*/__pycache__/*',
            '*/venv/*',
            '*/vendor/*',
            '*.tmp', '*.cache', '*.log',
            '*/Backup/*',  # Common backup folders
            '*/Cache/*',
            '*/.Trash/*'
        ]
    )
    
    # Dropbox
    if Path("/Users/phil/Library/CloudStorage/Dropbox").exists():
        indexer.add_volume(
            name="dropbox",
            mount_path="/Users/phil/Library/CloudStorage/Dropbox",
            index_name="dropbox",
            file_patterns=['*.pdf', '*.txt', '*.doc', '*.docx', '*.png', '*.jpg']
        )
    
    # pCloudSync (if different from pCloud Drive)
    if Path("/Users/phil/pCloudSync").exists():
        indexer.add_volume(
            name="pcloud_sync",
            mount_path="/Users/phil/pCloudSync",
            index_name="pcloud_sync",
            file_patterns=['*.pdf', '*.txt', '*.md']
        )
    
    return indexer


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
