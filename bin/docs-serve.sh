#!/bin/bash
# Se placer à la racine du projet
cd "$(dirname "$0")/.."

# Lancer mkdocs via le python du venv pour éviter les soucis de PATH
echo "Démarrage du serveur de documentation..."
echo "Ouvrez http://127.0.0.1:8001 dans votre navigateur"
echo "Logs: data/logs/docs.log"
nohup ./venv/bin/python -m mkdocs serve -a localhost:8001 > data/logs/docs.log 2>&1 &
echo "PID: $!"
