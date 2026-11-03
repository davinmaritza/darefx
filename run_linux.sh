#!/usr/bin/env bash

# DareFX Desktop GUI Launcher for Linux Mint
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Include local user-extracted Qt XCB cursor libraries
export LD_LIBRARY_PATH="/home/suzirz/.local/lib:${LD_LIBRARY_PATH}"
export DISPLAY="${DISPLAY:-:0}"
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Ensure SSH tunnel to VM 126 MT5 is established
if ! curl -s -m 1 http://127.0.0.1:8888/api/health >/dev/null 2>&1; then
    echo "Connecting to VM 126 MT5 via secure Proxmox tunnel..."
    pkill -f "8888:192.168.8.25:8888" 2>/dev/null || true
    ssh -f -N -L 8888:192.168.8.25:8888 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ConnectTimeout=5 root@208.84.103.84 2>/dev/null || true
    sleep 1
fi

echo "Starting DareFX Trading Station GUI..."
exec /home/suzirz/.local/bin/uv run --extra gui python app.py "$@"
