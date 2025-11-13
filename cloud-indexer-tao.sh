#!/usr/bin/env bash
#
# Cloud Indexer Management Script
# Manages the Indexao Cloud Indexer daemon via LaunchAgent
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_SOURCE="$PROJECT_ROOT/config/com.indexao.cloud-indexer.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.indexao.cloud-indexer.plist"
LABEL="com.indexao.cloud-indexer"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() { echo -e "${BLUE}ℹ${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warning() { echo -e "${YELLOW}⚠${NC} $*"; }
error() { echo -e "${RED}✗${NC} $*" >&2; }

# Check if daemon is loaded
is_loaded() {
    launchctl list | grep -q "$LABEL"
}

# Check if daemon is running
is_running() {
    launchctl list "$LABEL" &>/dev/null && 
    [[ $(launchctl list "$LABEL" | grep -c "PID") -eq 1 ]]
}

# Get daemon PID
get_pid() {
    if is_running; then
        launchctl list "$LABEL" | awk '/PID/ {print $3}'
    else
        echo "0"
    fi
}

# Install LaunchAgent
install() {
    info "Installing Cloud Indexer LaunchAgent..."
    
    # Copy plist to LaunchAgents
    cp "$PLIST_SOURCE" "$PLIST_DEST"
    success "Plist copied to $PLIST_DEST"
    
    # Load the agent
    launchctl load "$PLIST_DEST"
    success "LaunchAgent loaded"
    
    info "Cloud Indexer will start automatically when pCloud Drive is mounted"
}

# Uninstall LaunchAgent
uninstall() {
    info "Uninstalling Cloud Indexer LaunchAgent..."
    
    # Unload if loaded
    if is_loaded; then
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
        success "LaunchAgent unloaded"
    fi
    
    # Remove plist
    if [[ -f "$PLIST_DEST" ]]; then
        rm "$PLIST_DEST"
        success "Plist removed"
    fi
}

# Start daemon
start() {
    if is_loaded; then
        launchctl start "$LABEL"
        success "Cloud Indexer started"
    else
        error "LaunchAgent not installed. Run: $0 install"
        return 1
    fi
}

# Stop daemon
stop() {
    if is_loaded; then
        launchctl stop "$LABEL"
        success "Cloud Indexer stopped"
    else
        warning "LaunchAgent not loaded"
    fi
}

# Restart daemon
restart() {
    info "Restarting Cloud Indexer..."
    stop
    sleep 2
    start
}

# Reload daemon (reload plist config)
reload() {
    info "Reloading Cloud Indexer configuration..."
    
    if is_loaded; then
        launchctl unload "$PLIST_DEST"
    fi
    
    cp "$PLIST_SOURCE" "$PLIST_DEST"
    launchctl load "$PLIST_DEST"
    
    success "Configuration reloaded"
}

# Show daemon status
status() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Indexao Cloud Indexer Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if installed
    if [[ -f "$PLIST_DEST" ]]; then
        success "Installed: $PLIST_DEST"
    else
        error "Not installed"
        echo ""
        echo "To install: $0 install"
        return 1
    fi
    
    # Check if loaded
    if is_loaded; then
        success "LaunchAgent: Loaded"
    else
        warning "LaunchAgent: Not loaded"
    fi
    
    # Check if running
    pid=$(get_pid)
    if [[ "$pid" -ne 0 ]]; then
        success "Status: Running (PID: $pid)"
    else
        warning "Status: Not running"
    fi
    
    # Check pCloud mount
    if [[ -d "/Users/phil/pCloud Drive" ]]; then
        success "pCloud Drive: Mounted"
    else
        warning "pCloud Drive: Not mounted"
    fi
    
    echo ""
    
    # Show recent logs
    if [[ -f "$PROJECT_ROOT/logs/cloud-indexer.log" ]]; then
        echo "Recent logs (last 10 lines):"
        echo "─────────────────────────────────────────────"
        tail -n 10 "$PROJECT_ROOT/logs/cloud-indexer.log"
    fi
}

# Show logs
logs() {
    local lines="${1:-50}"
    
    if [[ -f "$PROJECT_ROOT/logs/cloud-indexer.log" ]]; then
        tail -n "$lines" -f "$PROJECT_ROOT/logs/cloud-indexer.log"
    else
        error "Log file not found: $PROJECT_ROOT/logs/cloud-indexer.log"
        return 1
    fi
}

# Manual scan (one-time)
scan() {
    local volume="${1:-}"
    
    cd "$PROJECT_ROOT"
    source venv/bin/activate
    
    if [[ -n "$volume" ]]; then
        info "Scanning volume: $volume"
        python -m indexao.cloud_indexer --scan "$volume"
    else
        info "Listing configured volumes:"
        python -m indexao.cloud_indexer --list
    fi
}

# Main command dispatcher
main() {
    local cmd="${1:-}"
    
    case "$cmd" in
        install)
            install
            ;;
        uninstall)
            uninstall
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        reload)
            reload
            ;;
        status)
            status
            ;;
        logs)
            logs "${2:-50}"
            ;;
        scan)
            scan "${2:-}"
            ;;
        *)
            cat <<EOF
Cloud Indexer Management Script

Usage:
  $0 <command> [options]

Commands:
  install       Install and enable LaunchAgent
  uninstall     Remove LaunchAgent
  start         Start the daemon
  stop          Stop the daemon
  restart       Restart the daemon
  reload        Reload configuration from plist
  status        Show daemon status
  logs [N]      Show last N lines of logs (default: 50)
  scan [volume] Manually scan a volume (one-time)

Examples:
  $0 install                  # Install the daemon
  $0 status                   # Check if running
  $0 logs 100                 # Show last 100 log lines
  $0 scan pcloud_drive        # Manually scan pCloud

EOF
            [[ -n "$cmd" ]] && error "Unknown command: $cmd"
            exit 1
            ;;
    esac
}

main "$@"
