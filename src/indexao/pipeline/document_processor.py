"""Document Processor Pipeline

Orchestre le traitement complet des documents :
Path Manager → OCR Adapter → Search Adapter

Flow:
1. Path Manager liste les fichiers d'un répertoire
2. Pour chaque fichier PDF/image → OCR extraction
3. Texte extrait → Indexation dans Meilisearch
4. Progress tracking et reporting
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import hashlib

from indexao.adapters.ocr.base import OCRAdapter
from indexao.adapters.search.base import SearchAdapter, IndexedDocument


class DocumentProcessor:
    """Processeur de documents avec pipeline OCR → Search.
    
    Utilise le Plugin Manager pour charger dynamiquement les adapters.
    Support multilingue (FR/EN/ZH-TW) avec auto-détection.
    
    Exemple:
        >>> from indexao.adapters.ocr import TesseractOCR
        >>> from indexao.adapters.search import MeilisearchAdapter
        >>> 
        >>> ocr = TesseractOCR()
        >>> search = MeilisearchAdapter()
        >>> processor = DocumentProcessor(ocr_adapter=ocr, search_adapter=search)
        >>> 
        >>> results = processor.process_directory(
        ...     directory=Path("/path/to/documents"),
        ...     language="fra+eng+chi_tra",
        ...     progress_callback=lambda p: print(f"Progress: {p['processed']}/{p['total']}")
        ... )
    """
    
    def __init__(
        self,
        ocr_adapter: OCRAdapter,
        search_adapter: SearchAdapter,
        supported_formats: Optional[List[str]] = None
    ):
        """Initialise le processeur.
        
        Args:
            ocr_adapter: Adaptateur OCR (ex: TesseractOCR)
            search_adapter: Adaptateur de recherche (ex: MeilisearchAdapter)
            supported_formats: Formats supportés (None = défaut PDF/images)
        """
        self.ocr = ocr_adapter
        self.search = search_adapter
        
        # Formats supportés par défaut
        if supported_formats is None:
            self.supported_formats = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
        else:
            self.supported_formats = supported_formats
    
    def process_directory(
        self,
        directory: Path,
        language: str = "fra+eng+chi_tra",
        recursive: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        filter_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """Traite tous les documents d'un répertoire.
        
        Args:
            directory: Chemin du répertoire à traiter
            language: Langue(s) pour OCR (ex: "fra+eng+chi_tra")
            recursive: Parcourir les sous-répertoires
            progress_callback: Fonction appelée avec progress updates
            filter_pattern: Pattern glob (ex: "*.pdf")
            
        Returns:
            {
                "total": int,
                "processed": int,
                "succeeded": int,
                "failed": int,
                "skipped": int,
                "errors": List[Dict],
                "processing_time": float
            }
        """
        start_time = datetime.now()
        
        # Collecter les fichiers
        files = self._collect_files(directory, recursive, filter_pattern)
        
        results = {
            "total": len(files),
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "processing_time": 0.0
        }
        
        # Traiter chaque fichier
        for i, file_path in enumerate(files, start=1):
            try:
                # Vérifier si déjà indexé (skip si oui)
                doc_id = self._generate_doc_id(file_path)
                existing = self.search.get_document(doc_id)
                
                if existing:
                    results["skipped"] += 1
                else:
                    # OCR + Indexation
                    success = self.process_file(file_path, language=language)
                    
                    if success:
                        results["succeeded"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append({
                            "file": str(file_path),
                            "error": "Processing failed"
                        })
                
                results["processed"] += 1
                
                # Callback de progression
                if progress_callback:
                    progress_callback({
                        "total": results["total"],
                        "processed": results["processed"],
                        "succeeded": results["succeeded"],
                        "failed": results["failed"],
                        "skipped": results["skipped"],
                        "current_file": file_path.name
                    })
            
            except Exception as e:
                results["failed"] += 1
                results["processed"] += 1
                results["errors"].append({
                    "file": str(file_path),
                    "error": str(e)
                })
        
        # Temps total
        results["processing_time"] = (datetime.now() - start_time).total_seconds()
        
        return results
    
    def process_file(
        self,
        file_path: Path,
        language: str = "fra+eng+chi_tra",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Traite un fichier unique.
        
        Args:
            file_path: Chemin du fichier
            language: Langue(s) pour OCR
            metadata: Métadonnées additionnelles
            
        Returns:
            True si succès, False sinon
        """
        try:
            # 1. OCR Extraction
            ocr_result = self.ocr.process_image(file_path, language=language)
            
            if not ocr_result.text or len(ocr_result.text.strip()) == 0:
                return False  # Pas de texte extrait
            
            # 2. Créer le document indexé
            doc_id = self._generate_doc_id(file_path)
            
            # Titre = nom du fichier sans extension
            title = file_path.stem
            
            # Déterminer la langue dominante (simple heuristique)
            detected_lang = self._detect_language(ocr_result.text, language)
            
            # Métadonnées enrichies
            doc_metadata = {
                "file_size": file_path.stat().st_size,
                "file_extension": file_path.suffix,
                "ocr_confidence": ocr_result.confidence,
                "ocr_engine": ocr_result.metadata.get("engine", "unknown"),
                "processing_time_ms": ocr_result.processing_time_ms,
                "pages": ocr_result.metadata.get("pages", 1)
            }
            
            if metadata:
                doc_metadata.update(metadata)
            
            indexed_doc = IndexedDocument(
                doc_id=doc_id,
                title=title,
                content=ocr_result.text,
                language=detected_lang,
                file_path=file_path,
                metadata=doc_metadata,
                created_at=datetime.fromtimestamp(file_path.stat().st_ctime),
                updated_at=datetime.fromtimestamp(file_path.stat().st_mtime)
            )
            
            # 3. Indexation dans Meilisearch
            success = self.search.index_document(indexed_doc)
            
            return success
        
        except Exception as e:
            print(f"Erreur traitement {file_path}: {e}")
            return False
    
    def _collect_files(
        self,
        directory: Path,
        recursive: bool = True,
        filter_pattern: Optional[str] = None
    ) -> List[Path]:
        """Collecte les fichiers à traiter.
        
        Args:
            directory: Répertoire de base
            recursive: Parcourir sous-répertoires
            filter_pattern: Pattern glob (ex: "*.pdf")
            
        Returns:
            Liste de chemins de fichiers
        """
        if not directory.exists() or not directory.is_dir():
            return []
        
        files = []
        
        if filter_pattern:
            # Utiliser le pattern glob
            if recursive:
                pattern_files = directory.rglob(filter_pattern)
            else:
                pattern_files = directory.glob(filter_pattern)
            
            files = [
                f for f in pattern_files
                if f.is_file() and f.suffix.lower() in self.supported_formats
            ]
        else:
            # Tous les fichiers supportés
            if recursive:
                all_files = directory.rglob("*")
            else:
                all_files = directory.glob("*")
            
            files = [
                f for f in all_files
                if f.is_file() and f.suffix.lower() in self.supported_formats
            ]
        
        return sorted(files)
    
    def _generate_doc_id(self, file_path: Path) -> str:
        """Génère un ID unique pour un fichier.
        
        Utilise le hash SHA256 du chemin absolu.
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            ID unique (hash)
        """
        path_str = str(file_path.absolute())
        return hashlib.sha256(path_str.encode()).hexdigest()[:16]
    
    def _detect_language(self, text: str, ocr_languages: str) -> str:
        """Détecte la langue dominante du texte.
        
        Simple heuristique basée sur les caractères.
        
        Args:
            text: Texte extrait
            ocr_languages: Langues utilisées pour OCR (ex: "fra+eng+chi_tra")
            
        Returns:
            Code langue ISO (fr, en, zh-TW)
        """
        # Compter les caractères par type
        latin_count = sum(1 for c in text if c.isalpha() and ord(c) < 0x2E80)
        chinese_count = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
        
        # Langue dominante
        if chinese_count > latin_count:
            return "zh-TW"
        
        # Pour FR/EN, on regarde les langues demandées
        if "fra" in ocr_languages:
            return "fr"
        elif "eng" in ocr_languages:
            return "en"
        else:
            return "fr"  # Défaut MVP
    
    def get_statistics(self) -> Dict[str, Any]:
        """Récupère les statistiques de l'index.
        
        Returns:
            {
                "total_documents": int,
                "by_language": {"fr": int, "en": int, "zh-TW": int},
                "search_backend": str,
                "ocr_engine": str
            }
        """
        return {
            "total_documents": self.search.count_documents(),
            "by_language": {
                "fr": self.search.count_documents(language="fr"),
                "en": self.search.count_documents(language="en"),
                "zh-TW": self.search.count_documents(language="zh-TW")
            },
            "search_backend": self.search.name,
            "ocr_engine": self.ocr.name
        }
