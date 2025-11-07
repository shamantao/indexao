"""Tesseract OCR Adapter

Implémentation réelle de l'extraction OCR avec Tesseract.
Utilise pytesseract pour l'OCR et pdf2image pour les PDFs scannés.
"""

import time
from pathlib import Path
from typing import List, Optional, Dict, Any

from indexao.adapters.ocr.base import OCRAdapter, OCRResult

try:
    import pytesseract  # type: ignore[import]
    from PIL import Image  # type: ignore[import]
    from pdf2image import convert_from_path  # type: ignore[import]
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False
    # Placeholders pour type checking
    pytesseract = None  # type: ignore
    Image = None  # type: ignore
    convert_from_path = None  # type: ignore


class TesseractOCR:
    """Adaptateur OCR basé sur Tesseract.
    
    Implémente le protocol OCRAdapter pour utilisation avec le Plugin Manager.
    
    Supporte:
    - Images: PNG, JPG, JPEG, TIFF, BMP
    - PDFs scannés: Convertis en images puis OCRisés
    
    Exemple:
        >>> ocr = TesseractOCR()
        >>> result = ocr.process_image(Path("facture.pdf"), language="fra")
        >>> print(result.text)
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """Initialise l'adaptateur Tesseract.
        
        Args:
            tesseract_cmd: Chemin vers l'exécutable Tesseract (optionnel)
                          Si None, utilise le PATH système
        """
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError(
                "Dependencies manquantes. Installez: pip install pytesseract pdf2image Pillow"
            )
        
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # Vérifier que Tesseract est disponible
        if not self.is_available():
            raise RuntimeError(
                "Tesseract n'est pas installé ou non accessible. "
                "Installez avec: brew install tesseract tesseract-lang (macOS)"
            )
    
    @property
    def name(self) -> str:
        """Nom de l'adaptateur."""
        return "tesseract"
    
    @property
    def supported_languages(self) -> List[str]:
        """Langues supportées (basé sur les packages installés)."""
        try:
            # Tesseract retourne les langues disponibles
            langs = pytesseract.get_languages(config='')
            return langs
        except Exception:
            # Fallback sur les plus communes
            return ["eng", "fra", "deu", "spa", "ita", "por", "rus", "chi_sim", "chi_tra"]
    
    def process_image(
        self,
        image_path: Path,
        language: Optional[str] = None,
        **kwargs
    ) -> OCRResult:
        """Extrait le texte d'un fichier image ou PDF.
        
        Args:
            image_path: Chemin vers le fichier à traiter
            language: Langue(s) pour Tesseract (ex: "fra", "fra+eng")
                     Si None, utilise "fra+eng" par défaut
            **kwargs: dpi (int), psm (int), oem (int)
            
        Returns:
            OCRResult avec texte extrait et métadonnées
        
        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si le format n'est pas supporté
        """
        start_time = time.time()
        
        if not image_path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {image_path}")
        
        # Langue par défaut
        if language is None:
            language = "fra+eng"
        
        suffix = image_path.suffix.lower()
        
        # PDF: Convertir en images puis OCR
        if suffix == ".pdf":
            text, confidence, pages = self._extract_from_pdf(
                image_path, language, kwargs.get("dpi", 300), **kwargs
            )
        
        # Image: OCR direct
        elif suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            text, confidence = self._extract_from_image(image_path, language, **kwargs)
            pages = 1
        
        else:
            raise ValueError(f"Format non supporté: {suffix}")
        
        processing_time = (time.time() - start_time) * 1000  # en ms
        
        return OCRResult(
            text=text,
            language=language,
            confidence=confidence,
            processing_time_ms=processing_time,
            metadata={
                "engine": "tesseract",
                "version": self.get_version(),
                "pages": pages,
                "file_format": suffix,
            }
        )
    
    def _extract_from_image(
        self,
        image_path: Path,
        language: str,
        **kwargs
    ) -> tuple[str, float]:
        """Extrait texte d'une image.
        
        Returns:
            (text, confidence)
        """
        img = Image.open(image_path)
        
        # Configuration Tesseract
        config = self._build_tesseract_config(**kwargs)
        
        # OCR
        text = pytesseract.image_to_string(img, lang=language, config=config)
        
        # Confidence (moyenne des mots)
        data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return text.strip(), avg_confidence / 100.0  # Convertir 0-100 → 0.0-1.0
    
    def _extract_from_pdf(
        self,
        pdf_path: Path,
        language: str,
        dpi: int = 300,
        **kwargs
    ) -> tuple[str, float, int]:
        """Extrait texte d'un PDF scanné.
        
        Returns:
            (text, confidence, pages)
        """
        # Convertir PDF → images
        images = convert_from_path(pdf_path, dpi=dpi)
        
        # OCR sur chaque page
        all_text = []
        all_confidences = []
        
        config = self._build_tesseract_config(**kwargs)
        
        for page_num, img in enumerate(images, start=1):
            text = pytesseract.image_to_string(img, lang=language, config=config)
            all_text.append(text.strip())
            
            # Confidence de cette page
            data = pytesseract.image_to_data(img, lang=language, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            if confidences:
                all_confidences.extend(confidences)
        
        # Moyenne globale
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        return (
            "\n\n".join(all_text),
            avg_confidence / 100.0,  # Convertir 0-100 → 0.0-1.0
            len(images)
        )
    
    def process_batch(
        self,
        image_paths: List[Path],
        language: Optional[str] = None,
        **kwargs
    ) -> List[OCRResult]:
        """Extrait texte de plusieurs images (batch processing).
        
        Args:
            image_paths: Liste de chemins vers les fichiers
            language: Langue(s) pour Tesseract
            **kwargs: Paramètres additionnels
            
        Returns:
            Liste de OCRResult (même ordre que input)
        """
        results = []
        for img_path in image_paths:
            try:
                result = self.process_image(img_path, language, **kwargs)
                results.append(result)
            except Exception as e:
                # En cas d'erreur, créer un résultat vide
                results.append(
                    OCRResult(
                        text="",
                        language=language or "fra+eng",
                        confidence=0.0,
                        processing_time_ms=0.0,
                        metadata={"error": str(e)}
                    )
                )
        return results
    
    def is_available(self) -> bool:
        """Vérifie que Tesseract est disponible."""
        try:
            version = pytesseract.get_tesseract_version()
            return version is not None
        except Exception:
            return False
    
    def get_version(self) -> str:
        """Retourne la version de Tesseract."""
        try:
            version = pytesseract.get_tesseract_version()
            return str(version)
        except Exception:
            return "unknown"

    
    def _build_tesseract_config(self, **kwargs) -> str:
        """Construit la chaîne de config Tesseract."""
        config_parts = []
        
        # PSM (Page Segmentation Mode): 3 = Auto
        psm = kwargs.get("psm", 3)
        config_parts.append(f"--psm {psm}")
        
        # OEM (OCR Engine Mode): 3 = Default (Legacy + LSTM)
        oem = kwargs.get("oem", 3)
        config_parts.append(f"--oem {oem}")
        
        return " ".join(config_parts)
    
    def supported_formats(self) -> list[str]:
        """Formats supportés."""
        return [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
    
    def health_check(self) -> bool:
        """Vérifie que Tesseract est disponible."""
        try:
            version = pytesseract.get_tesseract_version()
            return version is not None
        except Exception:
            return False
