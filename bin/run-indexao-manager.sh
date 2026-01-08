#!/bin/bash
# Lancement de l'app IndexaoManager menu bar

# Se placer dans le répertoire racine du projet (deux niveaux au-dessus de bin/)
cd "$(dirname "$0")/.."

# Activer l'environnement virtuel
source venv/bin/activate

# Lancer l'application en arrière-plan
echo "Lancement de Indexao Manager (Menu Bar)..."
PYTHONPATH="src:$PYTHONPATH" nohup python bin/legacy_gui/IndexaoManager.py > /dev/null 2>&1 &
PID=$!
echo "Indexao Manager démarré avec le PID $PID"
