import typer
from typing import Optional
from pathlib import Path
from indexao_core.config import load_config
from indexao_core.core.pipeline import Pipeline, parse_markdown
from indexao_core.core.scanner import VolumeScanner
from indexao_core.adapters.meilisearch import MeiliAdapter

app = typer.Typer()

@app.command()
def pack(file_path: str, force: bool = False):
    """
    Process a single file directly.
    """
    config = load_config()
    pipeline = Pipeline(config)
    
    path = Path(file_path)
    result = pipeline.process_file(path, force=force)
    
    status = result["status"]
    if status == "processed":
        typer.echo(f"✅ Processed: {path.name} -> {result['path']}")
    elif status == "skipped":
        typer.echo(f"⏭️  Skipped: {path.name} (Exists)")
    elif status == "error":
        typer.echo(f"❌ Error: {result['message']}")
    else:
        typer.echo(f"ℹ️  {status}: {result['message']}")

@app.command()
def scan(target: Optional[Path] = typer.Argument(None, help="Specific file or folder to scan"), force: bool = False, limit: int = 0):
    """
    Scan all configured volumes or a specific target.
    """
    config = load_config()
    scanner = VolumeScanner(config)
    pipeline = Pipeline(config)
    
    count_processed = 0
    count_skipped = 0
    count_errors = 0
    count_total = 0
    
    if target:
        typer.echo(f"🎯 Targeting Scan: {target}")
        file_iterator = scanner.scan_path(target)
    else:
        typer.echo(f"🚀 Starting Volume Scan...")
        file_iterator = scanner.scan_volumes()

    if file_iterator is None:
        return
    
    for file_path in file_iterator:
        if limit > 0 and count_total >= limit:
            typer.echo(f"\n⚠️ Limit of {limit} files reached. Stopping.")
            break

        count_total += 1
        
        # Visual feedback
        typer.echo(f"Processing: {file_path.name}...", nl=False)
        
        result = pipeline.process_file(file_path, force=force)
        status = result["status"]
        
        if status == "processed":
            typer.echo(f" ✅")
            count_processed += 1
        elif status == "skipped":
            typer.echo(f" ⏭️")
            count_skipped += 1
        elif status == "error":
            typer.echo(f" ❌ ({result['message']})")
            count_errors += 1
        else: # ignored/warning
            typer.echo(f" ⚪ ({result.get('message', '')})")

    typer.echo("\n--- Scan Complete ---")
    typer.echo(f"✅ Processed: {count_processed}")
    typer.echo(f"⏭️  Skipped:   {count_skipped}")
    typer.echo(f"❌ Errors:    {count_errors}")

@app.command()
def index(target: Optional[Path] = typer.Argument(None, help="Specific file or folder to index"), chunk_size: int = 100, clean: bool = typer.Option(False, help="Delete all documents before indexing")):
    """
    Index all Sidecar Markdown files into Meilisearch.
    """
    config = load_config()
    adapter = MeiliAdapter(config.meilisearch)
    scanner = VolumeScanner(config)
    
    if target:
        typer.echo(f"🎯 Targeting Index: {target}")
        file_iterator = scanner.scan_sidecars_in_path(target)
    else:
        typer.echo("🚀 Starting Indexation...")
        file_iterator = scanner.scan_sidecars()

    if file_iterator is None:
        typer.echo("❌ Invalid target.")
        return

    # Ensure index exists
    try:
        adapter.ensure_index()
    except Exception as e:
        typer.echo(f"❌ Error connecting to Meilisearch: {e}")
        return

    if clean:
        typer.echo("🧹 Clearing existing index...")
        adapter.clear_documents()
        import time
        time.sleep(1) # Give it a moment

    documents = []
    count = 0
    import hashlib
    
    for md_path in file_iterator:
        # Parse
        data = parse_markdown(md_path)
        metadata = data.get("metadata", {})
        content = data.get("content", "")
        translation = data.get("translation") # Can be None
        
        # Construct Document
        # ID: sha256 of original file if available, else hash of path
        doc_id = metadata.get("sha256")
        if not doc_id:
             doc_id = hashlib.sha256(str(md_path).encode()).hexdigest()
        
        doc = {
            "id": doc_id,
            "original_filename": metadata.get("original_filename", md_path.name),
            "content": content,
            "translation": translation, # New field
            "language": metadata.get("language", "unknown"),
            "tags": metadata.get("tags", []),
            "date_processed": metadata.get("date_processed"),
            "volume_path": str(md_path.parent)
        }
        
        documents.append(doc)
        
        if len(documents) >= chunk_size:
            adapter.add_documents(documents)
            count += len(documents)
            typer.echo(f" Indexed {len(documents)} docs... (Total: {count})")
            documents = []
            
    if documents:
        adapter.add_documents(documents)
        count += len(documents)
        
    typer.echo(f"\n✅ Indexation Complete: {count} documents processed.")

if __name__ == "__main__":
    app()
