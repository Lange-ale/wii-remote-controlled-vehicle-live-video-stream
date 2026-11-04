"""Flask web server for H.264 live streaming via MSE."""

import signal
import sys
from flask import Flask, Response, render_template
from camera import Camera

DEVICE = "/dev/video0"
WIDTH = 1280
HEIGHT = 720
FPS = 30
HOST = "0.0.0.0"
PORT = 5000
BITRATE = "2000k"

app = Flask(__name__)
camera = Camera(device=DEVICE, width=WIDTH, height=HEIGHT, fps=FPS, bitrate=BITRATE)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stream")
def stream():
    buf = camera.subscribe()

    def generate():
        try:
            while True:
                data = buf.read(timeout=2.0)
                if data is None:
                    break
                if data:
                    yield data
        finally:
            camera.unsubscribe(buf)

    resp = Response(generate(), mimetype="video/mp4")
    resp.headers["Cache-Control"] = "no-store, no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


def _shutdown(sig, _):
    print("\nShutting down...")
    camera.stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    print(f"Streaming: http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)
