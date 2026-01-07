#!/bin/bash
# Lancement de l'app IndexaoManager menu bar

# Se placer dans le répertoire racine du projet (deux niveaux au-dessus de bin/)
cd "$(dirname "$0")/.."

# Activer l'environnement virtuel
source venv/bin/activate

# Lancer l'application avec le PYTHONPATH correct incluant src/
PYTHONPATH="src:$PYTHONPATH" python bin/legacy_gui/IndexaoManager.py
