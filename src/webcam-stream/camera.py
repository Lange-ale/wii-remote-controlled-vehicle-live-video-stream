"""Camera module: captures H.264 fragmented MP4 from webcam via ffmpeg."""

import subprocess
import threading
import time


class ClientBuffer:
    """Thread-safe buffer for a single streaming client."""

    def __init__(self):
        self._chunks = []
        self._event = threading.Event()
        self._closed = False

    def append(self, data):
        self._chunks.append(data)
        self._event.set()

    def read(self, timeout=2.0):
        if self._closed:
            return None
        self._event.wait(timeout=timeout)
        if self._closed:
            return None
        self._event.clear()
        chunks = self._chunks
        self._chunks = []
        return b"".join(chunks) if chunks else b""

    def close(self):
        self._closed = True
        self._event.set()


class Camera:
    """Produces an H.264 fragmented MP4 stream from the webcam.

    ffmpeg encodes with minimal latency, outputting fMP4 on stdout pipe.
    Clients receive the init segment (ftyp+moov) first, then live chunks.
    """

    def __init__(self, device="/dev/video0", width=1280, height=720, fps=30, bitrate="2000k"):
        self._proc = subprocess.Popen(
            [
                "ffmpeg", "-loglevel", "warning",
                "-fflags", "+nobuffer+flush_packets",
                "-flags", "low_delay",
                "-probesize", "32",
                "-analyzeduration", "0",
                "-f", "v4l2",
                "-input_format", "mjpeg",
                "-video_size", f"{width}x{height}",
                "-framerate", str(fps),
                "-i", device,
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-profile:v", "baseline",
                "-level", "3.1",
                "-b:v", bitrate,
                "-maxrate", bitrate,
                "-bufsize", "150k",
                "-g", str(fps),
                "-keyint_min", str(fps),
                "-threads", "4",
                "-f", "mp4",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-frag_duration", "1",
                "-flush_packets", "1",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            bufsize=0,
        )
        self._lock = threading.Lock()
        self._clients = []
        self._running = True
        self._byte_count = 0
        self._bw_time = time.monotonic()
        self._init_segment = None
        self._init_ready = threading.Event()
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
        buf = bytearray()
        init_found = False

        while self._running:
            chunk = self._proc.stdout.read(32768)
            if not chunk:
                break

            if not init_found:
                buf.extend(chunk)
                moof_pos = buf.find(b"moof")
                if moof_pos >= 4:
                    init_end = moof_pos - 4
                    self._init_segment = bytes(buf[:init_end])
                    print(f"[CAM] Init segment: {len(self._init_segment)} bytes")
                    self._init_ready.set()
                    remainder = bytes(buf[init_end:])
                    init_found = True
                    buf = bytearray()
                    with self._lock:
                        for client_buf in self._clients:
                            client_buf.append(remainder)
                continue

            now = time.monotonic()
            self._byte_count += len(chunk)
            if now - self._bw_time >= 5.0:
                bw = self._byte_count / (now - self._bw_time) / 1024
                print(f"[CAM] {bw:.0f} KB/s | {len(self._clients)} client(s)")
                self._byte_count = 0
                self._bw_time = now

            with self._lock:
                for client_buf in self._clients:
                    client_buf.append(chunk)

    def subscribe(self):
        self._init_ready.wait(timeout=10)
        buf = ClientBuffer()
        if self._init_segment:
            buf.append(self._init_segment)
        with self._lock:
            self._clients.append(buf)
        return buf

    def unsubscribe(self, buf):
        with self._lock:
            try:
                self._clients.remove(buf)
            except ValueError:
                pass

    def stop(self):
        self._running = False
        with self._lock:
            for buf in self._clients:
                buf.close()
        # Graceful shutdown: send SIGTERM, wait for ffmpeg to close device cleanly
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Last resort — but this may crash the USB device
            self._proc.kill()
            self._proc.wait(timeout=3)
