#!/usr/bin/env bash

# Configuration
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$APP_DIR/indexao.pid"
LOG_FILE="$APP_DIR/indexao.log"
VENV_DIR="$APP_DIR/venv"
SRC_DIR="$APP_DIR/src"
APP_SCRIPT="$SRC_DIR/indexao_core/ui.py"
PYTHON_CMD="$VENV_DIR/bin/python"
STREAMLIT_CMD="$VENV_DIR/bin/streamlit"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ensure environment variables
export PYTHONPATH="$PYTHONPATH:$SRC_DIR"

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo -e "${RED}Indexao Dashboard is already running (PID: $PID)${NC}"
            return
        else
            echo "PID file exists but process is dead. Cleaning up."
            rm "$PID_FILE"
        fi
    fi

    echo -e "${GREEN}Starting Indexao Dashboard...${NC}"
    
    # Run Streamlit in background
    nohup "$STREAMLIT_CMD" run "$APP_SCRIPT" --server.port 8501 --server.headless true > "$LOG_FILE" 2>&1 &
    
    PID=$!
    echo $PID > "$PID_FILE"
    echo -e "Indexao started with PID $PID"
    echo -e "Logs available in $LOG_FILE"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${RED}Indexao is not running (no PID file)${NC}"
        return
    fi

    PID=$(cat "$PID_FILE")
    echo -e "${GREEN}Stopping Indexao Dashboard (PID: $PID)...${NC}"
    
    if kill $PID 2>/dev/null; then
        rm "$PID_FILE"
        echo "Stopped."
    else
        echo -e "${RED}Failed to stop process. It might not be running.${NC}"
        rm "$PID_FILE"
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo -e "${GREEN}Indexao Dashboard is running (PID: $PID)${NC}"
        else
            echo -e "${RED}Indexao Dashboard is NOT running (PID file exists but process is dead)${NC}"
        fi
    else
        echo "Indexao Dashboard is stopped."
    fi
}

scan() {
    echo -e "${GREEN}🚀 Starting Volume Scan (OCR + Sidecars)...${NC}"
    "$PYTHON_CMD" -m indexao_core.main scan "$@"
}

index() {
    # Default behavior: Force clean to ensure index matches disk
    # Override with --no-clean if needed manually but safer for user
    echo -e "${GREEN}🔎 Starting Indexation to Meilisearch (Safe Mode: Cleaning first)...${NC}"
    "$PYTHON_CMD" -m indexao_core.main index --clean "$@"
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    scan)
        shift
        scan "$@"
        ;;
    index)
        shift
        index "$@"
        ;;
    *)
        echo "Indexao Manager v2.0"
        echo "Usage: $0 {start|stop|restart|status|scan|index}"
        echo ""
        echo "Commands:"
        echo "  start   : Start the Web Dashboard (Streamlit)"
        echo "  stop    : Stop the Web Dashboard"
        echo "  restart : Restart the Web Dashboard"
        echo "  scan    : Scan volumes and generate sidecars (OCR)"
        echo "  index   : Index sidecars into Meilisearch"
        echo "  status  : Check dashboard status"
        exit 1
        ;;
esac