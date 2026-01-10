
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from indexao.cloud_indexer import CloudIndexer

def check_config():
    # Force use of the file we saw in logs
    state_path = Path("/Users/phil/pCloudSync/Projets/indexao/data/db/cloud_indexer_state.json")
    
    print(f"Checking state file: {state_path}")
    if not state_path.exists():
        print("ERROR: File does not exist!")
        return

    indexer = CloudIndexer(state_file=state_path)
    print(f"Loaded volumes: {len(indexer.state.volumes)}")
    
    for name, vol in indexer.state.volumes.items():
        print(f"Volume: {name}")
        print(f"  Patterns: {vol.file_patterns}")
        print(f"  Path: {vol.mount_path}")

if __name__ == "__main__":
    check_config()
