import sys
import os
from pathlib import Path

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), "src"))

from indexao.config import load_config, get_config

try:
    print("Loading config...")
    config = load_config()
    print(f"Config loaded from: {config.index_root}")
    print(f"DB Path resolved to: {config.db_path}")
    print(f"Index Root: {config.index_root}")
    
    print("\nPath Variables in Config Dict (Internal check):")
    # We can't easily access the internal dict from the Config object, 
    # but we can see the result.
    
    print(f"Home: {Path.home()}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
