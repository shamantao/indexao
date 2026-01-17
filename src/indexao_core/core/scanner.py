import os
import fnmatch
from pathlib import Path
from typing import List, Generator
from indexao_core.config import AppConfig

class VolumeScanner:
    def __init__(self, config: AppConfig):
        self.config = config
        
    def scan_volumes(self) -> Generator[Path, None, None]:
        """
        Yields file paths from all configured volumes that match inclusion criteria.
        """
        for volume in self.config.volumes:
            volume_path = Path(volume.path)
            if not volume_path.exists():
                print(f"⚠️ Volume not found: {volume.path}")
                continue
                
            print(f"📂 Scanning volume: {volume.path}")
            
            # Walk the directory
            for root, dirs, files in os.walk(volume_path):
                # Filter directories (in-place modification of dirs to prune)
                # Remove hidden dirs like .git
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                # Check exclusions for current directory
                # (Simple check for now, can be improved with pathspec)
                if self._is_excluded(Path(root), volume.exclude):
                    continue

                for file in files:
                    file_path = Path(root) / file
                    
                    if file.startswith('.'):
                        continue
                        
                    if file.endswith('.md'): # Don't scan our own sidecars or readme
                        continue
                        
                    if file == ".DS_Store":
                        continue

                    # Check file exclusions
                    if self._is_excluded(file_path, volume.exclude):
                        continue
                        
                    yield file_path

    def scan_sidecars(self) -> Generator[Path, None, None]:
        """Yields .md sidecar paths from all configured volumes."""
        for volume in self.config.volumes:
            volume_path = Path(volume.path)
            if not volume_path.exists():
                continue
                
            for root, dirs, files in os.walk(volume_path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                # Exclude directories
                # Note: We assume volumes are roots.
                # If we need full exclusion logic, we should refactor it.
                # Re-using _is_excluded roughly.
                
                for file in files:
                    if not file.endswith('.md'):
                        continue
                    
                    if file.startswith('.'):
                        continue
                        
                    file_path = Path(root) / file
                    
                    # We skip _is_excluded for valid sidecars if the pattern matches .md files?
                    # Generally, if the parent folder is excluded, we won't be here (dirs modification).
                    # If specific .md file is excluded, we honor it.
                    if self._is_excluded(file_path, volume.exclude):
                        continue
                        
                    yield file_path

    def _is_excluded(self, path: Path, exclude_patterns: List[str]) -> bool:
        """
        Check if path matches any exclude pattern.
        """
        # Normalize path to relative string or name for simple matching
        # Depending on pattern complexity.
        # Simple glob matching on the name or full path parts
        
        name = path.name
        str_path = str(path)
        
        for pattern in exclude_patterns:
            # Check simple name match
            if fnmatch.fnmatch(name, pattern):
                return True
            # Check path segments
            if pattern in str_path: # Very naive containment
                return True
                
        return False

    def scan_path(self, target: Path) -> Generator[Path, None, None]:
        """
        Yields file paths from a specific target (file or dir).
        Minimal exclusion rules apply (hidden files, .md, .DS_Store).
        """
        if not target.exists():
            print(f"⚠️ Target not found: {target}")
            return

        if target.is_file():
            # Basic checks for single file
            if target.name.startswith('.') or target.name.endswith('.md') or target.name == ".DS_Store":
                return
            yield target
            return

        # It's a directory
        print(f"📂 Scanning directory: {target}")
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                file_path = Path(root) / file
                
                if file.startswith('.'):
                    continue
                if file.endswith('.md') or file == ".DS_Store":
                    continue
                    
                yield file_path

    def scan_sidecars_in_path(self, target: Path) -> Generator[Path, None, None]:
        """
        Yields .md sidecar paths from a specific target (file or dir).
        """
        if not target.exists():
            # If the user passed a file path that doesn't exist, maybe they meant the sidecar?
            # Or if they passed "image.png" and "image.png.md" exists?
            # Let's handle the case where target points to the source file, checking for sidecar.
            sidecar_candidate = Path(str(target) + ".md")
            if sidecar_candidate.exists():
                 yield sidecar_candidate
            return

        if target.is_file():
            if target.name.endswith('.md'):
                yield target
            else:
                # If target is source file, look for adjacent .md
                sidecar_path = Path(str(target) + ".md")
                if sidecar_path.exists():
                    yield sidecar_path
            return

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.endswith('.md') and not file.startswith('.'):
                    yield Path(root) / file
