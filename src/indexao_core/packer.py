import typer
from pathlib import Path
from typing import Optional
import hashlib
import yaml
from datetime import datetime

from indexao_core.config import load_config
from indexao_core.core.detection import is_chinese_content
from indexao_core.adapters.ocr_apple import AppleVisionOCR

app = typer.Typer()

def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 of file content."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
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
        "tags": [] # Placeholder for future auto-tagging
    }
    
    # Frontmatter
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

@app.command()
def pack(file_path: str, force: bool = False):
    """
    Process a single file: OCR -> Detect -> Translate -> Save .md
    """
    path = Path(file_path)
    if not path.exists():
        typer.echo(f"Error: File {file_path} not found.")
        raise typer.Exit(code=1)
        
    config = load_config()
    
    # 1. Fingerprinting
    typer.echo(f"🔍 Analyzing {path.name}...")
    file_sha = calculate_sha256(path)
    
    # Target MD file
    md_path = path.with_suffix(".md")
    
    # Check if exists (Idempotence)
    if md_path.exists() and not force:
        # TODO: Read existing frontmatter to check SHA
        # For now, simplistic check
        typer.echo(f"⏭️  Sidecar already exists for {path.name}. Use --force to overwrite.")
        return

    # 2. Extraction
    try:
        # TODO: Switch extractor based on file type
        # For now, we assume PDF/Image and use Vision
        # In a full version, we'd have a Registry of Extractors
        
        if path.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.heic']:
            ocr = AppleVisionOCR()
            typer.echo("👁️  Extracting text with Apple Vision...")
            text = ocr.extract_text(str(path))
        elif path.suffix.lower() in ['.txt', '.md']:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
             typer.echo(f"⚠️  Unsupported file type: {path.suffix}")
             return
             
    except Exception as e:
        typer.echo(f"❌ Extraction failed: {e}")
        return

    # 3. Detection
    is_chinese = is_chinese_content(text, threshold=config.core.cjk_threshold)
    lang_code = "zh" if is_chinese else "en/fr"
    
    translation = None
    if is_chinese:
        typer.echo("🇨🇳 CJK Content detected (>5%). ")
        # TODO: Connect to LLM Adapter here
        typer.echo("🤖 [Mock] Sending to LLM for translation...")
        
        # Mock translation for MVP
        translation = "> (Simulation) Une traduction IA serait insérée ici.\n> Le document semble parler de..." 
        
    else:
        typer.echo("Latine Content detected. Skipping translation.")

    # 4. Persistence
    content = generate_markdown(
        original_path=path,
        extracted_text=text,
        original_sha=file_sha,
        language_code=lang_code,
        translation=translation
    )
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    typer.echo(f"✅ Generated sidecar: {md_path}")

if __name__ == "__main__":
    app()
