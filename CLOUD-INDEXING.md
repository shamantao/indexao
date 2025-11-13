# Indexation Multi-Cloud - Guide Complet

## 📋 Vue d'ensemble

Système d'indexation automatique et progressive pour plusieurs clouds avec **175k+ fichiers**.

### Architecture

- **Un index Meilisearch par cloud** (séparation logique)
- **Recherche unifiée** via multi-index de Meilisearch
- **Indexation progressive** par lots de 50-100 fichiers
- **Détection automatique** du montage des volumes
- **Reprise automatique** en cas d'interruption

## 🗂️ Volumes Configurés

| Volume           | Chemin                                     | Index Meilisearch | Statut          |
| ---------------- | ------------------------------------------ | ----------------- | --------------- |
| **pCloud Drive** | `/Users/phil/pCloud Drive`                 | `pcloud_drive`    | ✓ 175k fichiers |
| **Dropbox**      | `/Users/phil/Library/CloudStorage/Dropbox` | `dropbox`         | ✓ Monté         |
| **pCloudSync**   | `/Users/phil/pCloudSync`                   | `pcloud_sync`     | ✓ Monté         |

## 🚀 Démarrage Rapide

### 1. Scanner manuellement un volume (test)

```bash
cd /Users/phil/Library/CloudStorage/Dropbox/devwww/app/indexao
source venv/bin/activate

# Lister les volumes
python -m indexao.cloud_indexer --list

# Scanner pCloud Drive (mode test, sans indexer)
python -m indexao.cloud_indexer --scan pcloud_drive

# Scanner avec batch personnalisé
python -m indexao.cloud_indexer --scan pcloud_drive --batch-size 50
```

### 2. Lancer le daemon en arrière-plan

Le daemon surveille les volumes montés et indexe automatiquement :

```bash
# Option A: Via le script de gestion
./cloud-indexer-tao.sh install    # Installe le LaunchAgent
./cloud-indexer-tao.sh status     # Vérifie le statut
./cloud-indexer-tao.sh logs       # Voir les logs

# Option B: Manuellement (pour tester)
source venv/bin/activate
python -m indexao.cloud_indexer --daemon --batch-size 50
```

### 3. Installer le LaunchAgent (démarrage automatique)

```bash
./cloud-indexer-tao.sh install
```

Le daemon démarrera automatiquement quand pCloud Drive est monté !

## 📊 Surveillance et Gestion

### Vérifier le statut

```bash
./cloud-indexer-tao.sh status
```

Output attendu :

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Indexao Cloud Indexer Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Installed: ~/Library/LaunchAgents/com.indexao.cloud-indexer.plist
✓ LaunchAgent: Loaded
✓ Status: Running (PID: 12345)
✓ pCloud Drive: Mounted

Recent logs (last 10 lines):
─────────────────────────────────────────────
[2025-11-13] INFO Indexing batch 0-50 of 175171 files
[2025-11-13] INFO Progress: 50/175171 (0.0%)
```

### Voir les logs en temps réel

```bash
./cloud-indexer-tao.sh logs 100   # Dernières 100 lignes
./cloud-indexer-tao.sh logs       # Suivi en temps réel
```

### Commandes de gestion

```bash
./cloud-indexer-tao.sh stop       # Arrêter temporairement
./cloud-indexer-tao.sh start      # Redémarrer
./cloud-indexer-tao.sh restart    # Redémarrage complet
./cloud-indexer-tao.sh reload     # Recharger la config
./cloud-indexer-tao.sh uninstall  # Désinstaller complètement
```

## 🔧 Configuration

### Fichiers de configuration

- **LaunchAgent**: `config/com.indexao.cloud-indexer.plist`
- **État persistant**: `data/cloud_indexer_state.json`
- **Logs**: `logs/cloud-indexer.log`

### Modifier les patterns de fichiers

Éditez `src/indexao/cloud_indexer.py`, fonction `setup_default_volumes()` :

```python
indexer.add_volume(
    name="pcloud_drive",
    mount_path="/Users/phil/pCloud Drive",
    index_name="pcloud_drive",
    file_patterns=[
        '*.pdf', '*.txt', '*.doc', '*.docx',  # Documents
        '*.png', '*.jpg', '*.jpeg', '*.tiff', # Images
        '*.md', '*.html', '*.json'            # Autres
    ],
    exclude_patterns=[
        '*/.*',              # Fichiers cachés
        '*/node_modules/*',  # Dépendances
        '*/Backup/*',        # Backups
        '*.tmp', '*.cache'   # Temporaires
    ]
)
```

### Ajuster les performances

Dans `com.indexao.cloud-indexer.plist` :

```xml
<string>--batch-size</string>
<string>50</string>  <!-- Augmenter pour plus de vitesse (ex: 100) -->
```

Puis recharger :

```bash
./cloud-indexer-tao.sh reload
```

## 🔍 Recherche Multi-Cloud

### Option 1: Recherche dans tous les index (API directe)

```bash
# Chercher "facture" dans tous les clouds
curl -X POST 'http://localhost:7700/multi-search' \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "queries": [
      {"indexUid": "pcloud_drive", "q": "facture"},
      {"indexUid": "dropbox", "q": "facture"},
      {"indexUid": "pcloud_sync", "q": "facture"}
    ]
  }'
```

### Option 2: Via l'UI Indexao (à venir)

L'UI sera mise à jour pour permettre la recherche multi-cloud avec sélection des sources.

## 📈 Estimations de Performance

Pour **175 000 fichiers** sur pCloud Drive :

| Batch Size   | Temps estimé | CPU    | Mémoire |
| ------------ | ------------ | ------ | ------- |
| 50 fichiers  | ~58 heures   | Faible | ~200 MB |
| 100 fichiers | ~29 heures   | Moyen  | ~300 MB |
| 200 fichiers | ~14 heures   | Élevé  | ~500 MB |

**Recommandation** : Batch size de 50-100 pour un équilibre optimal.

L'indexation se fait **en arrière-plan** et reprend automatiquement si interrompue.

## 🛠️ Dépannage

### Le daemon ne démarre pas

```bash
# Vérifier les logs d'erreur
cat logs/cloud-indexer.error.log

# Tester manuellement
source venv/bin/activate
python -m indexao.cloud_indexer --list
```

### pCloud Drive non détecté

```bash
# Vérifier le montage
ls -la "/Users/phil/pCloud Drive"

# Si non monté, ouvrir l'app pCloud
open -a pCloudDrive
```

### Progression bloquée

```bash
# Voir l'état actuel
cat data/cloud_indexer_state.json

# Réinitialiser un volume
# Éditer data/cloud_indexer_state.json et mettre "indexed_files": 0
```

### Ralentir l'indexation

Modifier `cloud_indexer.py`, ligne ~230 :

```python
time.sleep(1)  # Pause entre batches (augmenter à 5 ou 10)
```

## 📝 État de l'Indexation

L'état est sauvegardé dans `data/cloud_indexer_state.json` :

```json
{
  "volumes": {
    "pcloud_drive": {
      "name": "pcloud_drive",
      "mount_path": "/Users/phil/pCloud Drive",
      "index_name": "pcloud_drive",
      "total_files": 175171,
      "indexed_files": 5000,
      "last_scan": "2025-11-13T12:30:00"
    }
  }
}
```

## 🎯 Prochaines Étapes

1. **Tester avec un scan manuel** :

   ```bash
   python -m indexao.cloud_indexer --scan pcloud_drive
   ```

2. **Installer le daemon si satisfait** :

   ```bash
   ./cloud-indexer-tao.sh install
   ```

3. **Surveiller les premières 100 fichiers** :

   ```bash
   ./cloud-indexer-tao.sh logs
   ```

4. **Créer les index Meilisearch via l'UI** :

   - http://indexao.localhost/config
   - Onglet "Gestion Meilisearch"
   - Créer : `pcloud_drive`, `dropbox`, `pcloud_sync`

5. **Implémenter l'intégration avec Meilisearch** (prochaine étape)

## 📚 Ressources

- **Documentation Meilisearch** : https://docs.meilisearch.com
- **Multi-Index Search** : https://docs.meilisearch.com/reference/api/multi_search.html
- **LaunchAgent Guide** : `man launchd.plist`

---

💡 **Astuce** : Commencez par indexer le volume le plus petit (Dropbox ou pCloudSync) pour valider le système avant de lancer pCloud Drive (175k fichiers).
