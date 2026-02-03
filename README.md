Indexao était un système intelligent d'indexation et de recherche documentaire basé sur l'OCR et la traduction automatique. Voici ses fonctions principales :

Objectif Principal
Créer un moteur de recherche local pour des documents PDF/images stockés sur le disque, avec extraction de texte (OCR) et traduction automatique.

Fonctionnalités Clés
OCR (Reconnaissance Optique de Caractères)

Extraction de texte depuis des PDF et images
Utilise Apple Vision (natif macOS)
Traduction Automatique

Détection intelligente de la langue
Traduction via Google Gemini API
Multi-clés API en rotation pour contourner les quotas
Système de Sidecar

Pour chaque document (contrat.pdf), création d'un fichier miroir (contrat.md)
Contient le texte extrait + traduction + métadonnées YAML
Indexation Meilisearch

Moteur de recherche local performant
Indexation séparée du contenu original et traduit
Interface Web (Streamlit)

🏠 Home : Moteur de recherche avec aperçu des résultats
📂 Explorer : Gestionnaire de fichiers pour piloter l'indexation
Architecture
Principe : "League of Truth" → le système de fichiers est la source absolue
Robustesse : L'index Meilisearch est jetable (peut être reconstruit)
Idempotence : Auto-healing des erreurs de traduction
C'était donc un outil puissant pour organiser, indexer et rechercher des documents locaux avec OCR et traduction ! 📚🔍
