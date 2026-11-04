#!/bin/bash
# Start both Camera server and WiiRemote controller
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== Starting Car System ==="
# Start camera server in background
echo "[1/2] Starting camera server..."
cd "$DIR/webcam-stream"
python3 app.py &
CAMERA_PID=$!
echo "       Camera PID: $CAMERA_PID"
# Start WiiRemote controller
echo "[2/2] Starting WiiRemote controller..."
cd "$DIR/wiimote"
bash run.sh start &
WIIMOTE_PID=$!
echo "       WiiRemote PID: $WIIMOTE_PID"
# Save PIDs for restart scripts
echo "$CAMERA_PID" > "$DIR/.camera.pid"
echo "$WIIMOTE_PID" > "$DIR/.wiimote.pid"
echo ""
echo "=== All systems running ==="
echo "Camera:    http://0.0.0.0:5000"
echo "WiiRemote: active"
echo ""
echo "Press Ctrl+C to stop all"
# Wait and cleanup on exit
trap "kill $CAMERA_PID $WIIMOTE_PID 2>/dev/null; rm -f $DIR/.camera.pid $DIR/.wiimote.pid; echo 'Stopped.'; exit 0" SIGINT SIGTERM
wait
