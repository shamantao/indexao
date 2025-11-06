#!/usr/bin/env python3
"""
Test du fix des chemins de logs

Ce script teste que les logs sont bien créés dans le bon répertoire après chargement config.
"""

from indexao.config import load_config
from indexao.logger import get_logger

logger = get_logger(__name__)

print("\n" + "="*70)
print("TEST: Fix des chemins de logs")
print("="*70)

print("\n[1] Avant load_config() - logs dans 'logs/' par défaut")
logger.info("Log avant chargement config")

print("\n[2] Chargement config.toml...")
config = load_config()

print(f"\n[3] Config chargée:")
print(f"  - log_dir: {config.logging.log_dir}")
print(f"  - Expected: /Users/phil/pCloudSync/Projets/indexao/data/logs")

print("\n[4] Après load_config() - logs dans config.logging.log_dir")
logger.info("Log après reconfiguration")
logger.debug("Debug log test")
logger.warning("Warning log test")

print("\n[5] Vérification...")
import os
from pathlib import Path

expected_dir = Path(config.logging.log_dir)
print(f"  - Expected dir exists: {expected_dir.exists()}")
print(f"  - Expected dir: {expected_dir}")

# List log files
if expected_dir.exists():
    log_files = list(expected_dir.glob("*.log"))
    print(f"  - Log files found: {len(log_files)}")
    for log_file in log_files[:3]:  # Show first 3
        print(f"    • {log_file.name}")

print("\n" + "="*70)
print("✅ Test terminé - Vérifiez que les logs sont dans le bon répertoire")
print("="*70)
