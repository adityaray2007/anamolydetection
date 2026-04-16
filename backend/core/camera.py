"""
Camera module - Handles DroidCam WiFi video capture with rolling frame buffer.
"""
import cv2
import time
import threading
import collections
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Camera:
    """Thread-safe camera capture with rolling frame buffer for event recording."""

    def __init__(self, source, buffer_seconds=10, fps=15, width=1280, height=720):
        self.source = source
        self.buffer_seconds = buffer_seconds
        self.target_fps = fps
        self.width = width
        self.height = height

        # Rolling buffer: stores (timestamp, frame) tuples
        max_frames = buffer_seconds * fps
        self.frame_buffer = collections.deque(maxlen=max_frames)

        self._current_frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cap = None
        self._connected = False
        self._retry_interval = 5  # seconds between reconnection attempts

    def start(self):
        """Start the camera capture thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"Camera started with source: {self.source}")

    def stop(self):
        """Stop the camera capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
        logger.info("Camera stopped")

    def _connect(self):
        """Connect to the camera source."""
        try:
            if self._cap:
                self._cap.release()

            logger.info(f"Connecting to camera: {self.source}")
            
            # Handle local camera IDs (e.g., "0", "1")
            source = self.source
            if isinstance(source, str) and source.isdigit():
                source = int(source)
                
            self._cap = cv2.VideoCapture(source)

            if isinstance(self.source, str) and self.source.startswith("http"):
                # DroidCam WiFi - set buffer size low for less latency
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            if self._cap.isOpened():
                self._connected = True
                logger.info("Camera connected successfully")
                return True
            else:
                self._connected = False
                logger.warning("Failed to open camera")
                return False
        except Exception as e:
            self._connected = False
            logger.error(f"Camera connection error: {e}")
            return False

    def _capture_loop(self):
        """Main capture loop running in a separate thread."""
        frame_interval = 1.0 / self.target_fps

        while self._running:
            if not self._connected:
                if not self._connect():
                    time.sleep(self._retry_interval)
                    continue

            start_time = time.time()
            
            try:
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("Failed to read frame, reconnecting...")
                    self._connected = False
                    time.sleep(1)
                    continue

                # Resize if needed
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))

                timestamp = time.time()
                
                with self._lock:
                    self._current_frame = frame.copy()
                    self.frame_buffer.append((timestamp, frame.copy()))

            except Exception as e:
                logger.error(f"Capture error: {e}")
                self._connected = False
                time.sleep(1)
                continue

            # Maintain target FPS
            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def get_frame(self):
        """Get the most recent frame (thread-safe)."""
        with self._lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
            return None

    def get_buffer_frames(self):
        """Get a copy of all buffered frames (for recording pre-event footage)."""
        with self._lock:
            return list(self.frame_buffer)

    def is_connected(self):
        """Check if camera is currently connected."""
        return self._connected

    def get_jpeg_frame(self, quality=80):
        """Get current frame encoded as JPEG bytes."""
        frame = self.get_frame()
        if frame is None:
            # Return a blank frame with "No Signal" text
            blank = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            cv2.putText(blank, "NO SIGNAL", (self.width // 2 - 200, self.height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
            cv2.putText(blank, "Waiting for camera connection...",
                        (self.width // 2 - 300, self.height // 2 + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (128, 128, 128), 2)
            frame = blank
        
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buffer.tobytes()
