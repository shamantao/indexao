#!/usr/bin/env python3
import sys
import logging
import requests
import typer
import subprocess
import re
from pathlib import Path
from typing import Optional

# Ensure src is in python path
sys.path.append(str(Path(__file__).parent / "src"))

from indexao_core.config import load_config, AppConfig

app = typer.Typer(help="Indexao Maintenance Doctor 🩺")

# Setup logging
log_file = Path("indexao.log") # Use main log
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - [DOCTOR] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Colors for CLI output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_result(message: str, status: str = "INFO"):
    """Log to file and print to console with color"""
    if status == "SUCCESS":
        print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")
        logging.info(f"SUCCESS: {message}")
    elif status == "WARNING":
        print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")
        logging.warning(message)
    elif status == "ERROR":
        print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")
        logging.error(message)
    elif status == "HEADER":
        print(f"\n{Colors.BOLD}{Colors.HEADER}--- {message} ---{Colors.ENDC}")
        logging.info(f"--- {message} ---")
    else:
        print(message)
        logging.info(message)

# --- Checks ---

def _check_api_keys(config: AppConfig):
    log_result("Checking Gemini API Keys", "HEADER")
    
    keys = config.llm.api_keys
    if not keys and config.llm.api_key:
        keys = [config.llm.api_key]
        
    if not keys:
        log_result("No API keys found in config!", "ERROR")
        return

    model = config.llm.model
    # Using generateContent entry point
    url_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    
    payload = {
        "contents": [{"parts": [{"text": "Ping"}]}]
    }
    headers = {'Content-Type': 'application/json'}

    valid_count = 0
    invalid_count = 0

    print(f"Testing {len(keys)} keys against model '{model}'...")

    for i, key in enumerate(keys):
        masked_key = f"...{key[-6:]}" if len(key) > 6 else "********"
        try:
            url = url_template.format(model=model, key=key)
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            
            if response.status_code == 200:
                log_result(f"Key #{i+1} ({masked_key}): Valid", "SUCCESS")
                valid_count += 1
            elif response.status_code == 400:
                log_result(f"Key #{i+1} ({masked_key}): INVALID/EXPIRED (400)", "ERROR")
                invalid_count += 1
            elif response.status_code == 429:
                log_result(f"Key #{i+1} ({masked_key}): QUOTA EXCEEDED (429)", "WARNING")
                valid_count += 1
            else:
                log_result(f"Key #{i+1} ({masked_key}): Error {response.status_code}", "ERROR")
                invalid_count += 1
                
        except Exception as e:
            log_result(f"Key #{i+1} ({masked_key}): Connection Error: {e}", "ERROR")
            invalid_count += 1

    print(f"Summary: {valid_count} Valid, {invalid_count} Invalid")

def _check_meilisearch(config: AppConfig):
    log_result("Checking Meilisearch Health", "HEADER")
    
    base_url = config.meilisearch.url
    api_key = config.meilisearch.api_key
    
    # 1. Ping
    try:
        r = requests.get(f"{base_url}/health", timeout=2)
        if r.status_code == 200:
             log_result("Meilisearch is running", "SUCCESS")
        else:
             log_result(f"Meilisearch responded with {r.status_code}", "WARNING")
    except requests.exceptions.ConnectionError:
        log_result(f"Meilisearch is down (Cannot connect to {base_url})", "ERROR")
        return

    # 2. Version Check & Comparison
    api_version = "Unknown"
    disk_version = "Unknown"

    # Get API Version
    try:
        r = requests.get(f"{base_url}/version", headers={"Authorization": f"Bearer {api_key}"}, timeout=2)
        if r.status_code == 200:
            api_version = r.json().get("pkgVersion", "Unknown")
        else:
             log_result("Could not fetch version from API", "WARNING")
    except Exception as e:
        log_result(f"API Version check failed: {e}", "ERROR")

    # Get Disk Version
    try:
        # Try finding meilisearch in path or common locations
        cmd = ["meilisearch", "--version"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            # Fallback for MacOS/Homebrew common path
            cmd = ["/opt/homebrew/bin/meilisearch", "--version"]
            res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode == 0:
            # Output format: "meilisearch 1.32.2"
            match = re.search(r'meilisearch (\d+\.\d+\.\d+)', res.stdout)
            if match:
                disk_version = match.group(1)
    except Exception:
        pass # Disk check is optional/diagnostic

    # Report
    if api_version != "Unknown" and disk_version != "Unknown":
        if api_version == disk_version:
            log_result(f"Version: {api_version} (Synced)", "SUCCESS")
        else:
            log_result(f"⚠️  Version Mismatch Detected!", "WARNING")
            print(f"   - Running in RAM:    {Colors.BOLD}{api_version}{Colors.ENDC}")
            print(f"   - Installed on Disk: {Colors.BOLD}{disk_version}{Colors.ENDC}")
            print(f"   👉 Recommendation: Run {Colors.OKBLUE}meilisearch-tao.sh upgrade{Colors.ENDC}")
    elif api_version != "Unknown":
        log_result(f"Meilisearch Version: {api_version}", "INFO")

    # 3. Stats / Index
    try:
        r = requests.get(f"{base_url}/indexes", headers={"Authorization": f"Bearer {api_key}"}, timeout=2)
        if r.status_code == 200:
            indexes = r.json().get("results", [])
            names = [idx['uid'] for idx in indexes]
            log_result(f"Indexes found: {names if names else 'None'}", "INFO")
        else:
            log_result(f"Could not list indexes ({r.status_code})", "ERROR")
    except Exception as e:
        log_result(f"Index check failed: {e}", "ERROR")

def _check_volumes_mount(config: AppConfig):
    log_result("Checking Volumes & Mounts", "HEADER")
    
    if not config.volumes:
        log_result("No volumes configured.", "WARNING")
        return

    for vol in config.volumes:
        path = Path(vol.path).expanduser().resolve()
        
        if not path.exists():
            log_result(f"Missing: {path}", "ERROR")
            continue
            
        if not path.is_dir():
             log_result(f"Not a directory: {path}", "ERROR")
             continue
             
        # Check empty (Mount point issue?)
        try:
            is_empty = not any(path.iterdir())
            if is_empty:
                log_result(f"Empty: {path} (Check Mount!)", "WARNING")
            else:
                log_result(f"Accessible: {path}", "SUCCESS")
        except PermissionError:
             log_result(f"Permission Denied: {path}", "ERROR")
        except Exception as e:
             log_result(f"Error accessing {path}: {e}", "ERROR")

def _find_orphans_in_path(target_path: Path):
    """Recursively find .md files without parent source"""
    for path in target_path.rglob("*.md"):
        # Assumption: indexao v2 creates file.pdf.md for file.pdf
        # If the sidecar is named 'name.md' -> source is 'name' (without last extension?)
        # Or 'name.pdf.md' -> source is 'name.pdf'
        
        # We need to deduce source file name.
        # Strict convention v2: source_file.md -> source_file
        
        # Check if it looks like a sidecar?
        # Just assume .md file name minus .md is the source
        source_name = path.with_suffix('') # remove .md
        
        if not source_name.exists():
            # Special case: README.md usually has no README source
            if path.name.lower() == "readme.md":
                continue
                
            print(f"{Colors.FAIL}Orphan found: {path}{Colors.ENDC}")
            # print(f"   (Source {source_name} missing)")

# --- Commands ---

@app.command()
def keys():
    """Check validity of configured API Keys."""
    _check_api_keys(load_config())

@app.command()
def meili():
    """Check Meilisearch status and version."""
    _check_meilisearch(load_config())

@app.command()
def volumes():
    """Check if volumes exist and are mounted (not empty)."""
    _check_volumes_mount(load_config())

@app.command()
def orphans(
    scope: str = typer.Argument("all", help="Scope: 'all' volumes or specific path"),
    dry: bool = True
):
    """
    Find orphan sidecar files (.md without source).
    Manual operation only.
    """
    config = load_config()
    log_result("Checking for Orphan Files", "HEADER")
    
    paths_to_scan = []
    
    if scope == "all":
        paths_to_scan = [Path(v.path).expanduser() for v in config.volumes]
    else:
        paths_to_scan = [Path(scope).expanduser()]
        
    for p in paths_to_scan:
        if not p.exists():
             log_result(f"Skipping missing path: {p}", "WARNING")
             continue
        print(f"Scanning {p} for orphans...")
        _find_orphans_in_path(p)
        
    print("\nNote: This tool lists files. Delete them manually using 'find' or similar if confirmed.")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Indexao Doctor 🩺 - Maintenance and Health Checks.
    Default: Runs all quick checks (Keys, Meili, Volumes).
    """
    if ctx.invoked_subcommand is None:
        # Default behavior: Run all non-intensive checks
        config = load_config()
        _check_volumes_mount(config)
        _check_meilisearch(config)
        _check_api_keys(config)
        print("\n💡 Tip: Run 'orphans' command manually to scan for dead sidecars.")

if __name__ == "__main__":
    app()
