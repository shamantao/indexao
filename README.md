# Indexao v2 - Core Reboot

## Philosophie : "Sidecar & Direct Connect"

Cette version **v2-core** marque une rupture architecturale avec la v1. L'objectif est la simplicité, la robustesse et la "vérité terrain".

### Principes Clés

1.  **League of Truth (L.O.T.)** : Le système de fichiers est la source de vérité absolue. Aucune métadonnée critique n'est enfermée *uniquement* dans une DB.
2.  **Sidecar Pattern** : Pour chaque document analysé (ex: `contrat.pdf`), un fichier miroir est créé (`contrat.md`). Il contient :
    *   Le texte extrait.
    *   La traduction (si nécessaire).
    *   Les métadonnées (SHA256, date, tags, langue) en Frontmatter YAML.
3.  **Idempotence** : L'index de recherche (Meilisearch) est *jetable*. Il peut être entièrement reconstruit à partir des fichiers Sidecar existants.
4.  **Triage Intelligent** : Pas d'IA aveugle. Une détection de langue décide si le document mérite une traduction coûteuse ou une simple indexation.

---

## Architecture Technique & Mises à jour (Jan 2026)

### 1. Le Pipeline ("The Walker")

Le processus de traitement est linéaire pour chaque fichier :

1.  **Détection** : Scan des volumes configurés ou **scan ciblé** sur un fichier/dossier spécifique.
2.  **Filtrage** : Exclusion via `config.toml` (patterns) et `.gitignore`.
3.  **Fingerprinting** : Calcul du SHA256. Vérification de l'existence du Sidecar.
4.  **Extraction (ETL)** :
    *   **PDF/Images** : OCR via **Apple Vision** (Natif macOS, via `pyobjc`).
5.  **Analyse & Traduction** :
    *   **Détection Langue** : Ratio de caractères CJK.
    *   **Moteur LLM** : **Google Gemini** (Round-Robin Multi-Keys).
       *   Utilisation de 4 clés API en rotation pour contourner les quotas.
       *   Gestion intelligente des erreurs 429 (Distinction entre Rate Limit temporaire et Quota Journalier épuisé).
       *   Modèle : `gemini-flash-latest`.
6.  **Génération Sidecar** : Format Markdown avec séparation claire :
    *   Frontmatter (YAML)
    *   `## 🇫🇷 Traduction (IA)`
    *   `## 📄 Texte Original (Extrait)`
7.  **Indexation Meilisearch** :
    *   Indexation distincte des champs `content` (original) et `translation` (traduit) pour une recherche précise.

### 2. Interface Utilisateur (UI)

*   **Technologie** : Streamlit
*   **Design** : Style "Finder" macOS / Explorateur de fichiers.
*   **Fonctionnalités** :
    *   Visualisation sous forme de cartes (File Cards) avec icônes.
    *   Boutons distincts pour ouvrir le fichier original ou la traduction.
    *   Affichage des extraits pertinents (Hit highlights) en jaune.

### 3. Stack

*   **Langage** : Python 3.12+ (managed by `venv`)
*   **CLI** : Typer
*   **OCR** : pyobjc-framework-Vision (macOS Native)
*   **Search** : Meilisearch (via client Python)
*   **LLM** : Google Gemini API (Multi-Key Load Balancing)
*   **Frontend** : Streamlit (Custom CSS)

---

## Utilisation (CLI)

Le script `indexao.sh` est le point d'entrée principal.

```bash
./indexao.sh [COMMAND] [ARGS]
```

### Tableau d'Aide

| Commande | Description | Argument Clé |
| :--- | :--- | :--- |
| `start` | Démarre l'interface Web (Streamlit) | - |
| `stop` | Arrête l'interface Web | - |
| `restart` | Redémarre l'interface Web | - |
| `scan` | Scan OCR + Traduction | `[path]` (Optionnel) |
| `index` | Indexation Meilisearch | `[path]` (Optionnel) |
| `status` | Vérifie l'état du service | - |

### Exemples d'Utilisation

**1. Scanner tous les volumes configurés :**
```bash
./indexao.sh scan
```

**2. Scanner un dossier ou un fichier spécifique (Ad-hoc) :**
```bash
./indexao.sh scan /Users/phil/Documents/Projet_X --force
```

**3. Indexer tout :**
```bash
./indexao.sh index --clean
```

**4. Indexer un fichier spécifique :**
*Détecte automatiquement le fichier .md associé au fichier source.*
```bash
./indexao.sh index /Users/phil/Documents/Contrat_Chinois.pdf
```

---

## Configuration (`config.toml`)

```toml
[core]
cjk_threshold = 0.05 

[meilisearch]
url = "http://localhost:7700"
api_key = "masterKey"

[llm]
api_keys = [
    "KEY_1",
    "KEY_2",
    "KEY_3",
    "KEY_4"
]
model = "gemini-flash-latest"
rpm = 15
daily_limit = 1500

[[volumes]]
path = "/Users/phil/Downloads/_Volumes"
scan_images = true
exclude = ["**/.DS_Store", "**/*.tmp"]
```
