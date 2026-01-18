import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

VOLUME_PATH = "/Users/phil/Downloads/_Volumes"

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

def audit():
    count_total = 0
    count_supported = 0
    count_sidecars_found = 0
    count_missing_sidecar = 0
    count_text_no_sidecar = 0
    
    count_trans_attempted = 0
    count_trans_success = 0
    count_trans_failed = 0
    count_trans_not_needed = 0

    supported_suffixes = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.heic', '.bmp', '.txt', '.py', '.xml', '.html']
    # .md excluded from source scan usually
    
    print(f"Auditing {VOLUME_PATH}...")
    
    root_path = Path(VOLUME_PATH)
    
    files_to_check = []
    
    for root, dirs, files in os.walk(VOLUME_PATH):
        for file in files:
            path = Path(root) / file
            if file.startswith('.'): continue
            
            # Skip existing sidecars from source check
            if file.endswith('.md'):
                # But we might check if this sidecar is orphan? 
                # Let's focus on Source -> Sidecar coverage
                continue
                
            count_total += 1
            if path.suffix.lower() in supported_suffixes:
                files_to_check.append(path)
            else:
                # print(f"Unsupported: {file}")
                pass

    count_supported = len(files_to_check)
    
    for source_path in files_to_check:
        sidecar_path = source_path.with_name(source_path.name + ".md")
        is_text = source_path.suffix.lower() in ['.txt', '.py', '.xml', '.html']
        
        if sidecar_path.exists():
            count_sidecars_found += 1
            
            # Analyze Sidecar
            try:
                data = parse_markdown(sidecar_path)
                metadata = data.get("metadata", {})
                translation = data.get("translation")
                content = data.get("content", "")
                
                lang = metadata.get("language", "unknown")
                
                # Check translation status
                # If lang is usually "zh" for our logic, or if translation field is present
                
                if translation:
                    count_trans_attempted += 1
                    if "> ⚠️" in translation:
                        count_trans_failed += 1
                        print(f"❌ Translation Failed: {source_path.name}")
                    else:
                        count_trans_success += 1
                        # print(f"✅ Translation OK: {source_path.name}")
                else:
                    count_trans_not_needed += 1
                    
            except Exception as e:
                print(f"Error reading sidecar {sidecar_path.name}: {e}")
                
        else:
            if is_text:
                count_text_no_sidecar += 1
            else:
                count_missing_sidecar += 1
                print(f"❌ Missing Sidecar: {source_path.name}")

    print("\n--- Audit Results ---")
    print(f"Total Files in Volume: {count_total}")
    print(f"Supported Source Files: {count_supported}")
    print(f"Sidecars Found: {count_sidecars_found}")
    print(f"Text Files (No Sidecar config): {count_text_no_sidecar}")
    print(f"Missing Sidecars (Errors/Skipped): {count_missing_sidecar}")
    print("-" * 20)
    print(f"Translations Attempted: {count_trans_attempted}")
    print(f"Translations Successful: {count_trans_success}")
    print(f"Translations Failed: {count_trans_failed}")
    print(f"Not Translated (En/Fr/Other): {count_trans_not_needed}")
    
if __name__ == "__main__":
    audit()
