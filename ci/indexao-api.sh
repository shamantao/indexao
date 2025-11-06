#!/usr/bin/env bash

###############################################################################
# Indexao API Management Script
# Usage: ./indexao-api.sh {start|stop|restart|status|reload|logs}
###############################################################################

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
PID_FILE="$PROJECT_DIR/indexao.pid"
LOG_FILE="$PROJECT_DIR/logs/webui.log"
HOST="127.0.0.1"
PORT="8000"

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

###############################################################################
# Fonctions utilitaires
###############################################################################

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

# Vérifier si l'environnement virtuel existe
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Environnement virtuel introuvable: $VENV_DIR"
        print_status "Créez-le avec: python3 -m venv venv"
        exit 1
    fi
}

# Obtenir le PID du processus
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        # Chercher le processus par port
        lsof -ti:$PORT 2>/dev/null | head -n 1
    fi
}

# Vérifier si le serveur est en cours d'exécution
is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

###############################################################################
# Commandes principales
###############################################################################

# Afficher le statut du serveur
status() {
    print_status "Vérification du statut de l'API Indexao..."
    
    if is_running; then
        local pid=$(get_pid)
        print_success "API en cours d'exécution (PID: $pid)"
        print_status "URL: http://$HOST:$PORT"
        
        # Vérifier la connectivité
        if command -v curl &> /dev/null; then
            if curl -s "http://$HOST:$PORT/health" > /dev/null 2>&1; then
                print_success "API répond correctement"
            else
                print_warning "API ne répond pas sur /health"
            fi
        fi
        
        # Afficher les infos du processus
        echo ""
        print_status "Détails du processus:"
        ps -p $pid -o pid,ppid,%cpu,%mem,etime,command 2>/dev/null || echo "Impossible d'obtenir les détails"
        
    else
        print_warning "API non démarrée"
        
        # Nettoyer le PID file s'il existe
        if [ -f "$PID_FILE" ]; then
            rm -f "$PID_FILE"
            print_status "Fichier PID obsolète supprimé"
        fi
    fi
}

# Démarrer le serveur
start() {
    print_status "Démarrage de l'API Indexao..."
    
    if is_running; then
        print_warning "API déjà en cours d'exécution (PID: $(get_pid))"
        print_status "Utilisez 'restart' pour redémarrer"
        exit 1
    fi
    
    check_venv
    
    # Créer le répertoire logs si nécessaire
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Activer l'environnement virtuel et démarrer le serveur
    print_status "Activation de l'environnement virtuel..."
    cd "$PROJECT_DIR"
    
    source "$VENV_DIR/bin/activate"
    
    print_status "Lancement du serveur sur http://$HOST:$PORT"
    
    # Démarrer en arrière-plan
    nohup python -m indexao.webui > "$LOG_FILE" 2>&1 &
    local pid=$!
    
    # Sauvegarder le PID
    echo $pid > "$PID_FILE"
    
    # Attendre un peu pour vérifier que le serveur démarre
    sleep 2
    
    if is_running; then
        print_success "API démarrée avec succès (PID: $pid)"
        print_status "Logs: $LOG_FILE"
        print_status "URL: http://$HOST:$PORT"
        
        # Afficher les dernières lignes du log
        echo ""
        print_status "Dernières lignes du log:"
        tail -n 5 "$LOG_FILE"
    else
        print_error "Échec du démarrage de l'API"
        print_status "Consultez les logs: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Arrêter le serveur
stop() {
    print_status "Arrêt de l'API Indexao..."
    
    if ! is_running; then
        print_warning "API non démarrée"
        rm -f "$PID_FILE"
        exit 0
    fi
    
    local pid=$(get_pid)
    print_status "Arrêt du processus $pid..."
    
    # Envoi du signal SIGTERM
    kill -TERM "$pid" 2>/dev/null
    
    # Attendre l'arrêt (max 10 secondes)
    local count=0
    while is_running && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo ""
    
    # Si toujours en cours, forcer l'arrêt
    if is_running; then
        print_warning "Arrêt forcé (SIGKILL)..."
        kill -9 "$pid" 2>/dev/null
        sleep 1
    fi
    
    if is_running; then
        print_error "Impossible d'arrêter le processus $pid"
        exit 1
    else
        print_success "API arrêtée"
        rm -f "$PID_FILE"
    fi
}

# Redémarrer le serveur
restart() {
    print_status "Redémarrage de l'API Indexao..."
    stop
    sleep 1
    start
}

# Recharger sans cache (restart + clear cache)
reload() {
    print_status "Rechargement de l'API (sans cache)..."
    
    # Arrêter le serveur
    if is_running; then
        stop
    fi
    
    # Nettoyer les caches Python
    print_status "Nettoyage des caches Python..."
    cd "$PROJECT_DIR"
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find . -type f -name "*.pyc" -delete 2>/dev/null
    find . -type f -name "*.pyo" -delete 2>/dev/null
    print_success "Caches nettoyés"
    
    # Redémarrer
    sleep 1
    start
}

# Afficher les logs en temps réel
logs() {
    if [ ! -f "$LOG_FILE" ]; then
        print_error "Fichier de log introuvable: $LOG_FILE"
        exit 1
    fi
    
    print_status "Affichage des logs (Ctrl+C pour quitter)..."
    echo ""
    tail -f "$LOG_FILE"
}

# Afficher l'aide
usage() {
    cat << EOF
${BLUE}Indexao API Management Script${NC}

${GREEN}Usage:${NC}
    $0 {start|stop|restart|status|reload|logs}

${GREEN}Commandes:${NC}
    ${YELLOW}start${NC}      Démarrer l'API
    ${YELLOW}stop${NC}       Arrêter l'API
    ${YELLOW}restart${NC}    Redémarrer l'API
    ${YELLOW}status${NC}     Afficher le statut de l'API
    ${YELLOW}reload${NC}     Redémarrer sans cache (nettoie __pycache__)
    ${YELLOW}logs${NC}       Afficher les logs en temps réel

${GREEN}Exemples:${NC}
    $0 start          # Démarrer le serveur
    $0 status         # Vérifier si le serveur tourne
    $0 reload         # Redémarrer en nettoyant les caches
    $0 logs           # Suivre les logs en temps réel

${GREEN}Configuration:${NC}
    Host:     $HOST
    Port:     $PORT
    PID File: $PID_FILE
    Logs:     $LOG_FILE
    Venv:     $VENV_DIR

EOF
}

###############################################################################
# Point d'entrée principal
###############################################################################

case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    reload)
        reload
        ;;
    logs)
        logs
        ;;
    *)
        usage
        exit 1
        ;;
esac