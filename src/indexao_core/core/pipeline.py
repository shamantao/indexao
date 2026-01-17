import hashlib
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from indexao_core.config import AppConfig
from indexao_core.core.detection import is_chinese_content
from indexao_core.adapters.ocr_apple import AppleVisionOCR
from indexao_core.adapters.translation_gemini import GeminiAdapter

def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 of file content."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def generate_markdown(
    original_path: Path,
    extracted_text: str,
    original_sha: str,
    language_code: str,
    translation: Optional[str] = None
) -> str:
    """Generate the content of the Sidecar Markdown file."""
    
    metadata = {
        "original_filename": original_path.name,
        "sha256": original_sha,
        "language": language_code,
        "date_processed": datetime.now().isoformat(),
        "tags": []
    }
    
    content = "---\n"
    content += yaml.dump(metadata, default_flow_style=False)
    content += "---\n\n"
    
    content += f"# {original_path.name}\n\n"
    
    if translation:
        content += "## 🇫🇷 Traduction (IA)\n\n"
        content += f"{translation}\n\n"
        content += "---\n\n"
        content += "## 📄 Texte Original (Extrait)\n\n"
    else:
        content += "## 📄 Contenu Extrait\n\n"
        
    content += f"{extracted_text}\n"
    
    return content

def parse_markdown(file_path: Path) -> Dict[str, Any]:
    """Parse a Sidecar Markdown file to extract metadata, content AND translation."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        metadata = {}
        body = content
        
        # Extract YAML frontmatter
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                    body = parts[2]
                except yaml.YAMLError:
                    pass
        
        # Intelligent split of Translation vs Content
        translation_text = None
        main_content = body.strip()
        
        # Check for our known separators (defined in generate_markdown)
        marker_trans = "## 🇫🇷 Traduction (IA)"
        marker_orig = "## 📄 Texte Original (Extrait)"
        
        if marker_trans in body and marker_orig in body:
            # We have a translation block
            # Format is: Header -> Trans -> Separator -> Header -> Original
            
            # Split by translation header first
            _, rest = body.split(marker_trans, 1)
            
            # Split by original header
            if marker_orig in rest:
                trans_part, orig_part = rest.split(marker_orig, 1)
                
                # Cleanup headers and separators from the parts
                translation_text = trans_part.replace("---\n", "").strip()
                main_content = orig_part.strip()

        return {
            "metadata": metadata,
            "content": main_content,
            "translation": translation_text
        }
    except Exception:
        return {"metadata": {}, "content": "", "translation": None}

class Pipeline:
    def __init__(self, config: AppConfig):
        self.config = config
        self.ocr = AppleVisionOCR()
        self.translator = GeminiAdapter(config.llm)

    def process_file(self, path: Path, force: bool = False) -> Dict[str, Any]:
        """
        Process a single file: Identity -> Extract -> Detect -> Save.
        Returns a result dict.
        """
        if not path.exists():
            return {"status": "error", "message": "File not found"}
            
        # 1. Identity (Fingerprint)
        file_sha = calculate_sha256(path)
        # Use appended extension to avoid collisions (e.g. file.json vs file.pdf)
        md_path = path.with_name(path.name + ".md")
        
        # Check idempotence
        if md_path.exists() and not force:
            # OPTIONAL: Read existing SHA to confirm it matches current file
            # For speed, usually we trust mtime or just skip.
            # Here we skip if exists.
            return {"status": "skipped", "message": "Sidecar exists", "path": str(md_path)}

        # 2. Extraction
        try:
            suffix = path.suffix.lower()
            text = ""
            is_text_source = False
            
            if suffix in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.heic', '.bmp']:
                text = self.ocr.extract_text(str(path))
            elif suffix in ['.txt', '.md', '.py', '.xml', '.html']:
                # Text files: just read them
                is_text_source = True
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            else:
                 return {"status": "ignored", "message": f"Unsupported type: {suffix}"}
                 
        except Exception as e:
            return {"status": "error", "message": f"Extraction failed: {str(e)}"}

        if not text.strip():
             return {"status": "warning", "message": "No text extracted"}

        # Optimization: Don't create sidecar for text files if configured
        if is_text_source and not self.config.core.sidecar_for_text_files:
             # We skip persistence, but return success so it can be indexed directly later
             # (Note: Current Indexer design relies on MD. If we skip MD, we need to index original.)
             # For now, let's treat it as "skipped persistence"
             return {
                 "status": "processed_no_sidecar", 
                 "path": str(path),
                 "message": "Direct text file (no sidecar generated)"
            }

        # 3. Detection
        # Use simple detection first
        is_chinese = is_chinese_content(text, threshold=self.config.core.cjk_threshold)
        lang_code = "zh" if is_chinese else "en/fr"
        
        translation = None
        translation_failed = False
        if is_chinese:
            # Automatic Translation via Gemini
            try:
                # Limit text for translation to avoid token limits or huge latencies 
                # (Gemini Flash has ~1M context so it's fine, but let's be reasonable)
                # Maybe take first 30k chars for now?
                trans_text = text[:30000] 
                
                print(f"   🤖 Translating {path.name} ({len(trans_text)} chars)...", end="", flush=True)
                translation_result = self.translator.translate(trans_text)
                
                if translation_result:
                    translation = translation_result
                    print(" OK")
                else:
                    translation = "> ⚠️ Traduction échouée (API Error)\n"
                    translation_failed = True
                    print(" Failed")
            except Exception as e:
                translation = f"> ⚠️ Erreur traduction: {str(e)}\n"
                translation_failed = True
                print(f" Error: {e}")
        
        # 4. Persistence
        content = generate_markdown(
            original_path=path,
            extracted_text=text,
            original_sha=file_sha,
            language_code=lang_code,
            translation=translation
        )
        
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
             return {"status": "error", "message": f"Write failed: {str(e)}"}
            
        return {
            "status": "processed", 
            "path": str(md_path), 
            "language": lang_code,
            "chinese_detected": is_chinese,
            "translation_failed": translation_failed
        }
