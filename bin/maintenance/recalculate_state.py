#!/usr/bin/env python3
"""
Recalculate cloud_indexer_state.json from the actual queue database.
This fixes the discrepancy between queue reality and state file.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from indexao.database import DocumentDatabase

def main():
    # Load current state
    state_file = Path("data/cloud_indexer_state.json")
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    print("📊 Current state (from JSON):")
    for name, vol in state['volumes'].items():
        print(f"  {name}: {vol['indexed_files']}/{vol['total_files']} files, last_scan={vol['last_scan']}")
    
    # Query actual queue stats
    db = DocumentDatabase()
    with db._connection() as conn:
        cursor = conn.execute("""
            SELECT volume, status, COUNT(*) as count 
            FROM index_queue 
            GROUP BY volume, status
            ORDER BY volume, status
        """)
        
        stats = {}
        for row in cursor:
            volume = row['volume']
            status = row['status']
            count = row['count']
            if volume not in stats:
                stats[volume] = {'total': 0, 'done': 0, 'pending': 0, 'processing': 0, 'error': 0}
            stats[volume][status] = count
            stats[volume]['total'] += count
    
    print("\n📊 Queue reality (from SQLite):")
    for volume, data in stats.items():
        print(f"  {volume}: {data['done']}/{data['total']} done, {data['pending']} pending, {data['error']} errors")
    
    # Update state
    print("\n🔄 Updating state file...")
    for volume_name, data in stats.items():
        if volume_name in state['volumes']:
            vol = state['volumes'][volume_name]
            vol['total_files'] = data['total']
            vol['indexed_files'] = data['done']
            if data['done'] > 0:
                vol['last_scan'] = datetime.now().isoformat()
            print(f"  Updated {volume_name}: {vol['indexed_files']}/{vol['total_files']}")
    
    # Save
    state['last_updated'] = datetime.now().isoformat()
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"\n✅ State file updated: {state_file}")

if __name__ == "__main__":
    main()
