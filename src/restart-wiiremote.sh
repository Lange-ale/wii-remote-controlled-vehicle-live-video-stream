#!/bin/bash
# Restart WiiRemote controller
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Restarting WiiRemote controller..."

# Kill existing
if [[ -f "$DIR/.wiimote.pid" ]]; then
    OLD_PID=$(cat "$DIR/.wiimote.pid")
    kill "$OLD_PID" 2>/dev/null && echo "Stopped old process (PID $OLD_PID)"
fi

# Also kill any lingering CarControl process
sudo pkill -f "CarControl" 2>/dev/null

# Start fresh
cd "$DIR/wiimote"
bash run.sh start &
NEW_PID=$!
echo "$NEW_PID" > "$DIR/.wiimote.pid"

echo "WiiRemote controller restarted (PID $NEW_PID)"
