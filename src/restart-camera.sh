#!/bin/bash
# Restart camera server — graceful shutdown to avoid USB crash
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Restarting camera server..."

# Graceful stop: SIGTERM only (never SIGKILL — it crashes the USB webcam)
if [[ -f "$DIR/.camera.pid" ]]; then
    OLD_PID=$(cat "$DIR/.camera.pid")
    sudo kill "$OLD_PID" 2>/dev/null && echo "Stopped app (PID $OLD_PID)"
    # Wait for process to actually exit
    for i in $(seq 1 10); do
        kill -0 "$OLD_PID" 2>/dev/null || break
        sleep 0.3
    done
fi

# Kill any lingering python camera process (SIGTERM only)
sudo pkill -TERM -f "python3.*webcam-stream/app.py" 2>/dev/null
sleep 0.5

# Kill ffmpeg gracefully with SIGTERM (lets it close the device cleanly)
sudo pkill -TERM -f "ffmpeg.*/dev/video" 2>/dev/null

# Wait for ffmpeg to exit and device to be released
echo -n "Waiting for device release..."
for i in $(seq 1 10); do
    ! sudo fuser /dev/video0 2>/dev/null && break
    echo -n "."
    sleep 0.5
done
echo ""

# Wait for /dev/video0 to exist (USB re-enumeration)
echo -n "Waiting for /dev/video0..."
for i in $(seq 1 30); do
    [[ -e /dev/video0 ]] && break
    echo -n "."
    sleep 0.5
done
echo ""

if [[ ! -e /dev/video0 ]]; then
    echo "WARNING: /dev/video0 not found, attempting USB port reset..."
    echo '1-1.3' | sudo tee /sys/bus/usb/drivers/usb/unbind >/dev/null 2>&1
    sleep 2
    echo '1-1.3' | sudo tee /sys/bus/usb/drivers/usb/bind >/dev/null 2>&1
    for i in $(seq 1 20); do
        [[ -e /dev/video0 ]] && break
        sleep 0.5
    done
fi

if [[ ! -e /dev/video0 ]]; then
    echo "ERROR: /dev/video0 not found. Webcam may need physical reconnect."
    exit 1
fi

echo "Device ready."

# Start fresh
cd "$DIR/webcam-stream"
python3 app.py &
NEW_PID=$!
echo "$NEW_PID" > "$DIR/.camera.pid"

echo "Camera server restarted (PID $NEW_PID)"
echo "http://0.0.0.0:5000"
