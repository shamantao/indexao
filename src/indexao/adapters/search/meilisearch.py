"""Meilisearch Search Adapter

Implémentation réelle de l'indexation et recherche avec Meilisearch.
Moteur de recherche ultra-rapide avec typo-tolerance et recherche sémantique.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from indexao.adapters.search.base import SearchAdapter, IndexedDocument, SearchResult

try:
    import meilisearch
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False
    meilisearch = None  # type: ignore


class MeilisearchAdapter:
    """Adaptateur de recherche basé sur Meilisearch.
    
    Implémente le protocol SearchAdapter pour intégration avec le Plugin Manager.
    
    Caractéristiques:
    - Recherche full-text ultra-rapide (<100ms)
    - Typo-tolerance (1-2 caractères)
    - Filtres et facettes
    - Highlighting des résultats
    - Multi-langue (FR, EN, ZH)
    - Indexation batch performante
    
    Exemple:
        >>> adapter = MeilisearchAdapter(host="http://127.0.0.1:7700")
        >>> doc = IndexedDocument(
        ...     doc_id="invoice_123",
        ...     title="Facture EDF 2024",
        ...     content="Montant TTC: 150.50 EUR",
        ...     language="fr"
        ... )
        >>> adapter.index_document(doc)
        >>> results = adapter.search("facture edf", limit=10)
    """
    
    def __init__(
        self,
        host: str = "http://127.0.0.1:7700",
        api_key: Optional[str] = None,
        index_name: str = "documents"
    ):
        """Initialise l'adaptateur Meilisearch.
        
        Args:
            host: URL du serveur Meilisearch
            api_key: Clé API (None pour serveur local sans auth)
            index_name: Nom de l'index à utiliser
        """
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError(
                "Dépendances manquantes. Installez: pip install meilisearch"
            )
        
        self.host = host
        self.index_name = index_name
        
        # Connexion au client
        self.client = meilisearch.Client(host, api_key)
        
        # Créer/récupérer l'index
        self.index = self._get_or_create_index()
        
        # Configurer les paramètres de recherche
        self._configure_index()
    
    def _get_or_create_index(self) -> meilisearch.index.Index:
        """Récupère ou crée l'index Meilisearch."""
        try:
            # Essayer de récupérer l'index existant
            return self.client.get_index(self.index_name)
        except Exception:
            # Créer l'index s'il n'existe pas
            task = self.client.create_index(self.index_name, {"primaryKey": "doc_id"})
            self.client.wait_for_task(task.task_uid)
            return self.client.get_index(self.index_name)
    
    def _configure_index(self):
        """Configure les paramètres de l'index (searchable, filterable, etc.)."""
        # Champs cherchables
        self.index.update_searchable_attributes([
            "title",
            "content",
            "metadata"
        ])
        
        # Champs filtrables
        self.index.update_filterable_attributes([
            "language",
            "created_at",
            "updated_at",
            "file_path"
        ])
        
        # Champs triables
        self.index.update_sortable_attributes([
            "created_at",
            "updated_at"
        ])
        
        # Typo tolerance configurée (1-2 caractères acceptés)
        self.index.update_typo_tolerance({
            "enabled": True,
            "minWordSizeForTypos": {
                "oneTypo": 5,
                "twoTypos": 9
            }
        })
        
        # Support multilingue (FR, EN, ZH-TW)
        # Meilisearch détecte automatiquement le chinois et applique la segmentation
        # Pas besoin de configuration spéciale pour ZH-TW
        # Référence: https://www.meilisearch.com/docs/learn/what_is_meilisearch/language
    
    @property
    def name(self) -> str:
        """Nom de l'adaptateur."""
        return "meilisearch"
    
    def index_document(self, document: IndexedDocument) -> bool:
        """Indexe un document unique.
        
        Args:
            document: Document à indexer
            
        Returns:
            True si succès, False sinon
        """
        try:
            # Convertir en dict pour Meilisearch
            doc_dict = {
                "doc_id": document.doc_id,
                "title": document.title,
                "content": document.content,
                "language": document.language,
                "file_path": str(document.file_path) if document.file_path else None,
                "metadata": document.metadata,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat()
            }
            
            task = self.index.add_documents([doc_dict])
            self.client.wait_for_task(task.task_uid)
            
            return True
        except Exception as e:
            print(f"Erreur indexation: {e}")
            return False
    
    def index_batch(self, documents: List[IndexedDocument]) -> int:
        """Indexe plusieurs documents (batch).
        
        Args:
            documents: Liste de documents
            
        Returns:
            Nombre de documents indexés avec succès
        """
        if not documents:
            return 0
        
        try:
            # Convertir tous les documents
            docs_dict = []
            for doc in documents:
                docs_dict.append({
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "content": doc.content,
                    "language": doc.language,
                    "file_path": str(doc.file_path) if doc.file_path else None,
                    "metadata": doc.metadata,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat()
                })
            
            task = self.index.add_documents(docs_dict)
            self.client.wait_for_task(task.task_uid)
            
            return len(documents)
        except Exception as e:
            print(f"Erreur indexation batch: {e}")
            return 0
    
    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        language: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Recherche des documents.
        
        Args:
            query: Requête de recherche
            limit: Nombre max de résultats
            offset: Décalage (pagination)
            language: Filtre par langue
            filters: Filtres additionnels
            
        Returns:
            Liste de SearchResult triés par pertinence
        """
        try:
            # Construire les filtres Meilisearch
            filter_str = None
            if language:
                filter_str = f"language = {language}"
            
            # Options de recherche
            search_params = {
                "limit": limit,
                "offset": offset,
                "attributesToHighlight": ["content", "title"],
                "highlightPreTag": "<mark>",
                "highlightPostTag": "</mark>"
            }
            
            if filter_str:
                search_params["filter"] = filter_str
            
            # Effectuer la recherche
            results = self.index.search(query, search_params)
            
            # Convertir en SearchResult
            search_results = []
            for hit in results.get("hits", []):
                # Extraire highlight ou snippet
                formatted = hit.get("_formatted", {})
                content_snippet = formatted.get("content", hit.get("content", ""))[:300]
                
                # Calculer score (Meilisearch retourne pas de score normalisé, on utilise le rank)
                # Position dans les résultats comme proxy de score
                rank = results["hits"].index(hit)
                score = 1.0 - (rank / max(len(results["hits"]), 1))
                
                search_results.append(
                    SearchResult(
                        doc_id=hit["doc_id"],
                        title=hit["title"],
                        content_snippet=content_snippet,
                        score=score,
                        language=hit["language"],
                        metadata=hit.get("metadata", {}),
                        highlights=[]  # TODO: extraire les highlights
                    )
                )
            
            return search_results
        
        except Exception as e:
            print(f"Erreur recherche: {e}")
            return []
    
    def get_document(self, doc_id: str) -> Optional[IndexedDocument]:
        """Récupère un document par ID.
        
        Args:
            doc_id: Identifiant du document
            
        Returns:
            IndexedDocument si trouvé, None sinon
        """
        try:
            doc = self.index.get_document(doc_id)
            
            return IndexedDocument(
                doc_id=doc["doc_id"],
                title=doc["title"],
                content=doc["content"],
                language=doc["language"],
                file_path=Path(doc["file_path"]) if doc.get("file_path") else None,
                metadata=doc.get("metadata", {}),
                created_at=datetime.fromisoformat(doc["created_at"]),
                updated_at=datetime.fromisoformat(doc["updated_at"])
            )
        except Exception:
            return None
    
    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un document.
        
        Args:
            doc_id: Identifiant
            updates: Champs à mettre à jour
            
        Returns:
            True si succès
        """
        try:
            updates["doc_id"] = doc_id
            updates["updated_at"] = datetime.now().isoformat()
            
            task = self.index.update_documents([updates])
            self.client.wait_for_task(task.task_uid)
            
            return True
        except Exception as e:
            print(f"Erreur update: {e}")
            return False
    
    def delete_document(self, doc_id: str) -> bool:
        """Supprime un document.
        
        Args:
            doc_id: Identifiant
            
        Returns:
            True si succès
        """
        try:
            task = self.index.delete_document(doc_id)
            self.client.wait_for_task(task.task_uid)
            return True
        except Exception as e:
            print(f"Erreur suppression: {e}")
            return False
    
    def count_documents(self, language: Optional[str] = None) -> int:
        """Compte les documents.
        
        Args:
            language: Filtre par langue
            
        Returns:
            Nombre de documents
        """
        try:
            if language:
                results = self.search("", limit=0, language=language)
                return results.get("estimatedTotalHits", 0) if isinstance(results, dict) else 0
            else:
                stats = self.index.get_stats()
                return stats.get("numberOfDocuments", 0)
        except Exception:
            return 0
    
    def clear_index(self) -> bool:
        """Vide l'index complètement.
        
        Returns:
            True si succès
        """
        try:
            task = self.index.delete_all_documents()
            self.client.wait_for_task(task.task_uid)
            return True
        except Exception as e:
            print(f"Erreur clear: {e}")
            return False
    
    def is_available(self) -> bool:
        """Vérifie que Meilisearch est disponible.
        
        Returns:
            True si le serveur répond
        """
        try:
            health = self.client.health()
            return health.get("status") == "available"
        except Exception:
            return False
    
    def get_version(self) -> str:
        """Retourne la version de Meilisearch.
        
        Returns:
            Version string
        """
        try:
            version = self.client.get_version()
            return version.get("pkgVersion", "unknown")
        except Exception:
            return "unknown"
