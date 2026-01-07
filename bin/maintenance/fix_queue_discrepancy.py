#!/usr/bin/env python3
"""
Fix the discrepancy between queue (66321 done) and Meilisearch (50042 docs).
The root cause: Document IDs with parentheses were rejected by Meilisearch.
Solution: Reset to pending and reprocess with fixed ID generation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from indexao.database import DocumentDatabase
import httpx

def main():
    print("\n" + "="*70)
    print("🔍 DIAGNOSTIC DE L'ÉCART QUEUE VS MEILISEARCH")
    print("="*70 + "\n")
    
    # Check Meilisearch
    url = "http://localhost:7700"
    try:
        response = httpx.get(f"{url}/indexes/pcloud_drive/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            meilisearch_count = stats.get("numberOfDocuments", 0)
            print(f"📊 Documents dans Meilisearch (pcloud_drive): {meilisearch_count:,}")
        else:
            print(f"❌ Erreur Meilisearch: {response.status_code}")
            return
            
        # Check failed tasks
        tasks_resp = httpx.get(f"{url}/tasks?indexUids=pcloud_drive&statuses=failed", timeout=5)
        if tasks_resp.status_code == 200:
            failed_count = tasks_resp.json().get("total", 0)
            print(f"❌ Tâches Meilisearch échouées: {failed_count}")
            
            # Show first error
            if failed_count > 0:
                detail_resp = httpx.get(f"{url}/tasks?indexUids=pcloud_drive&statuses=failed&limit=1", timeout=5)
                if detail_resp.status_code == 200:
                    first_error = detail_resp.json()["results"][0]
                    error_msg = first_error.get("error", {}).get("message", "N/A")
                    print(f"   Exemple d'erreur: {error_msg[:100]}...")
                    
    except Exception as e:
        print(f"❌ Erreur connexion Meilisearch: {e}")
        return
    
    # Check queue
    db = DocumentDatabase()
    with db._connection() as conn:
        cursor = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM index_queue
            WHERE volume = 'pcloud_drive'
            GROUP BY status
        """)
        queue_stats = {}
        total_queue = 0
        for row in cursor:
            status = row["status"]
            count = row["count"]
            queue_stats[status] = count
            total_queue += count
            print(f"   {status}: {count:,}")
        
        print(f"\n📊 Total dans la queue (pcloud_drive): {total_queue:,}")
        ecart = queue_stats.get("done", 0) - meilisearch_count
        print(f"⚠️  Écart: {ecart:,} documents manquants dans Meilisearch\n")
    
    print("="*70)
    print("🔧 CAUSE IDENTIFIÉE:")
    print("   Les IDs avec parenthèses () sont invalides pour Meilisearch")
    print("   Exemple: 'pcloud_drive_photo(1)_12345' → Rejeté")
    print("   Solution: Nettoyer les IDs et réindexer")
    print("="*70 + "\n")
    
    # Ask user
    response = input("Voulez-vous réinitialiser les fichiers 'done' en 'pending' pour réindexation? (oui/non): ")
    if response.lower() not in ['oui', 'o', 'yes', 'y']:
        print("\n❌ Annulé")
        return
    
    # Reset to pending
    with db._connection() as conn:
        cursor = conn.execute("""
            UPDATE index_queue
            SET status = 'pending', indexed_at = NULL
            WHERE volume = 'pcloud_drive' AND status = 'done'
        """)
        updated = cursor.rowcount
        print(f"\n✅ {updated:,} fichiers remis en attente")
    
    print("\n" + "="*70)
    print("🚀 PROCHAINES ÉTAPES:")
    print("="*70)
    print("1. Surveillez la page monitoring: http://127.0.0.1:8000/monitoring")
    print("2. Lancez le scan pour traiter la queue:")
    print("   curl -X POST http://127.0.0.1:8000/api/cloud/volumes/pcloud_drive/scan")
    print("\n   OU dans Python:")
    print("   python3 -c \"from indexao.cloud_indexer import setup_default_volumes;")
    print("              idx = setup_default_volumes();")
    print("              vol = idx.state.volumes['pcloud_drive'];")
    print("              idx.index_volume_progressive(vol)\"")
    print("\n3. Les IDs seront maintenant nettoyés (pas de parenthèses)")
    print("4. La page monitoring se mettra à jour automatiquement toutes les 3s")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
