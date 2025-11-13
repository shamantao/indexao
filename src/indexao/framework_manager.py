"""
Framework Manager - Handles local JS/CSS frameworks with CDN fallback.

This module provides:
- Local framework file management
- Automatic CDN fallback if local files fail
- Version checking and updates
- Integration with PluginManager
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import urllib.request
import urllib.error

from indexao.logger import get_logger

logger = get_logger(__name__)


class Framework:
    """Represents a JavaScript or CSS framework."""
    
    def __init__(
        self,
        name: str,
        local_path: str,
        cdn_url: str,
        version: Optional[str] = None,
        check_url: Optional[str] = None
    ):
        self.name = name
        self.local_path = local_path
        self.cdn_url = cdn_url
        self.version = version
        self.check_url = check_url or cdn_url
        
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "local_path": self.local_path,
            "cdn_url": self.cdn_url,
            "version": self.version,
            "check_url": self.check_url
        }


class FrameworkManager:
    """Manages JavaScript and CSS frameworks with local storage and CDN fallback."""
    
    FRAMEWORKS = {
        "alpine": Framework(
            name="Alpine.js",
            local_path="/static/js/vendor/alpine.min.js",
            cdn_url="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js",
            version="3.14.1"
        ),
        "htmx": Framework(
            name="HTMX",
            local_path="/static/js/vendor/htmx.min.js",
            cdn_url="https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js",
            version="1.9.10"
        ),
        "fontawesome": Framework(
            name="FontAwesome",
            local_path="/static/css/vendor/fontawesome.min.css",
            cdn_url="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
            version="6.4.0"
        )
    }
    
    def __init__(self, static_dir: Path):
        """
        Initialize framework manager.
        
        Args:
            static_dir: Path to static directory (e.g., src/indexao/static)
        """
        self.static_dir = static_dir
        self.js_vendor = static_dir / "js" / "vendor"
        self.css_vendor = static_dir / "css" / "vendor"
        self.state_file = static_dir / "frameworks.json"
        
        # Create directories if needed
        self.js_vendor.mkdir(parents=True, exist_ok=True)
        self.css_vendor.mkdir(parents=True, exist_ok=True)
        
        self.state = self._load_state()
        logger.info(f"Framework manager initialized: {static_dir}")
    
    def _load_state(self) -> dict:
        """Load framework state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load framework state: {e}")
        return {}
    
    def _save_state(self):
        """Save framework state to JSON file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save framework state: {e}")
    
    def get_framework_path(self, framework_key: str) -> str:
        """
        Get the best available path for a framework (local or CDN).
        
        Args:
            framework_key: Key from FRAMEWORKS dict (e.g., 'alpine', 'htmx')
            
        Returns:
            Path to use (local if available, CDN as fallback)
        """
        fw = self.FRAMEWORKS.get(framework_key)
        if not fw:
            logger.warning(f"Unknown framework requested: {framework_key}")
            return ""
        
        # Check if local file exists
        local_file = self._get_local_file_path(fw)
        if local_file.exists() and local_file.stat().st_size > 0:
            logger.debug(f"Using local framework: {fw.name} at {fw.local_path}")
            return fw.local_path
        
        # Fallback to CDN
        logger.info(f"Local framework {fw.name} not found, using CDN")
        return fw.cdn_url
    
    def _get_local_file_path(self, fw: Framework) -> Path:
        """Get absolute filesystem path for a framework."""
        # Remove leading /static/
        relative = fw.local_path.replace("/static/", "")
        return self.static_dir / relative
    
    def download_framework(self, framework_key: str) -> bool:
        """
        Download a framework from CDN to local storage.
        
        Args:
            framework_key: Key from FRAMEWORKS dict
            
        Returns:
            True if successful, False otherwise
        """
        fw = self.FRAMEWORKS.get(framework_key)
        if not fw:
            logger.error(f"Unknown framework: {framework_key}")
            return False
        
        local_file = self._get_local_file_path(fw)
        
        try:
            with logger.timer(f"download_{fw.name}"):
                logger.info(f"Downloading framework {fw.name} from {fw.cdn_url}")
                
                # Download with timeout
                req = urllib.request.Request(
                    fw.cdn_url,
                    headers={'User-Agent': 'Indexao/1.0'}
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read()
                
                # Save to file
                local_file.parent.mkdir(parents=True, exist_ok=True)
                local_file.write_bytes(content)
                
                # Update state
                self.state[framework_key] = {
                    "downloaded": datetime.now().isoformat(),
                    "version": fw.version,
                    "size": len(content)
                }
                self._save_state()
                
                logger.info(
                    f"Framework {fw.name} downloaded successfully: "
                    f"{len(content)/1024:.1f}KB to {local_file}"
                )
                return True
                
        except Exception as e:
            logger.error(f"Failed to download framework {fw.name}: {e}")
            return False
    
    def download_all(self) -> Dict[str, bool]:
        """
        Download all frameworks.
        
        Returns:
            Dict mapping framework keys to success status
        """
        results = {}
        for key in self.FRAMEWORKS:
            results[key] = self.download_framework(key)
        return results
    
    def check_updates(self) -> List[str]:
        """
        Check which frameworks need updates.
        
        Returns:
            List of framework keys that need updating
        """
        needs_update = []
        
        for key, fw in self.FRAMEWORKS.items():
            local_file = self._get_local_file_path(fw)
            
            # Missing file
            if not local_file.exists():
                needs_update.append(key)
                continue
            
            # Check last download date
            fw_state = self.state.get(key)
            if not fw_state:
                needs_update.append(key)
                continue
            
            try:
                downloaded = datetime.fromisoformat(fw_state["downloaded"])
                # Update if older than 30 days
                if datetime.now() - downloaded > timedelta(days=30):
                    needs_update.append(key)
            except (KeyError, ValueError):
                needs_update.append(key)
        
        return needs_update
    
    def get_status(self) -> Dict[str, dict]:
        """
        Get status of all frameworks.
        
        Returns:
            Dict with framework info and availability status
        """
        status = {}
        
        for key, fw in self.FRAMEWORKS.items():
            local_file = self._get_local_file_path(fw)
            fw_state = self.state.get(key, {})
            
            status[key] = {
                "name": fw.name,
                "version": fw.version,
                "local_available": local_file.exists(),
                "local_size": local_file.stat().st_size if local_file.exists() else 0,
                "local_path": fw.local_path,
                "cdn_url": fw.cdn_url,
                "last_downloaded": fw_state.get("downloaded"),
                "needs_update": key in self.check_updates()
            }
        
        return status
    
    def generate_html_tags(self, framework_key: str) -> str:
        """
        Generate HTML script/link tag with CDN fallback.
        
        Args:
            framework_key: Key from FRAMEWORKS dict
            
        Returns:
            HTML tag(s) as string
        """
        fw = self.FRAMEWORKS.get(framework_key)
        if not fw:
            return ""
        
        path = self.get_framework_path(framework_key)
        
        if fw.local_path.endswith('.js'):
            # JavaScript with fallback
            if path == fw.local_path:
                return f'''<script src="{fw.local_path}" onerror="loadCDN('{framework_key}')"></script>
<script>
function loadCDN(fw) {{
    if (fw === '{framework_key}') {{
        const script = document.createElement('script');
        script.src = '{fw.cdn_url}';
        document.head.appendChild(script);
    }}
}}
</script>'''
            else:
                return f'<script src="{fw.cdn_url}"></script>'
        
        elif fw.local_path.endswith('.css'):
            # CSS with fallback
            if path == fw.local_path:
                return f'<link rel="stylesheet" href="{fw.local_path}" onerror="this.onerror=null; this.href=\'{fw.cdn_url}\'">'
            else:
                return f'<link rel="stylesheet" href="{fw.cdn_url}">'
        
        return ""


# Global instance
_manager: Optional[FrameworkManager] = None


def get_framework_manager() -> FrameworkManager:
    """Get the global FrameworkManager instance."""
    global _manager
    if _manager is None:
        from pathlib import Path
        static_dir = Path(__file__).parent / "static"
        _manager = FrameworkManager(static_dir)
    return _manager


def ensure_frameworks_available() -> bool:
    """
    Ensure all frameworks are available locally.
    Downloads missing ones.
    
    Returns:
        True if all frameworks are available
    """
    manager = get_framework_manager()
    needs_update = manager.check_updates()
    
    if needs_update:
        logger.info(f"Downloading {len(needs_update)} missing frameworks")
        results = manager.download_all()
        return all(results.values())
    
    return True
