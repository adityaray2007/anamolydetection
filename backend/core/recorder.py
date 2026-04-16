"""
Event Recorder - Records video clips around detected events.
Saves pre-event + post-event footage as MP4 files.
"""
import os
import cv2
import time
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EventRecorder:
    """Records event clips using the camera's frame buffer."""

    def __init__(self, recordings_dir, camera, pre_seconds=10, post_seconds=10, fps=15):
        self.recordings_dir = recordings_dir
        self.camera = camera
        self.pre_seconds = pre_seconds
        self.post_seconds = post_seconds
        self.fps = fps
        self._recording = False
        self._lock = threading.Lock()
        
        os.makedirs(recordings_dir, exist_ok=True)

    def record_event(self, alert_type, description=""):
        """
        Start recording an event clip in background.
        Returns the path where the recording will be saved.
        """
        with self._lock:
            if self._recording:
                logger.info("Already recording an event, skipping")
                return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{alert_type}_{timestamp}.mp4"
        filepath = os.path.join(self.recordings_dir, filename)

        thread = threading.Thread(
            target=self._record_clip,
            args=(filepath, alert_type, description),
            daemon=True
        )
        thread.start()

        return filepath

    def _record_clip(self, filepath, alert_type, description):
        """Record a clip with pre-event buffer + post-event footage."""
        with self._lock:
            self._recording = True

        try:
            logger.info(f"Recording event: {alert_type} -> {filepath}")

            # Get pre-event frames from buffer
            pre_frames = self.camera.get_buffer_frames()
            
            if not pre_frames:
                logger.warning("No pre-event frames in buffer")
                frame = self.camera.get_frame()
                if frame is not None:
                    pre_frames = [(time.time(), frame)]

            # Determine video properties from first frame
            if pre_frames:
                _, sample_frame = pre_frames[0]
                height, width = sample_frame.shape[:2]
            else:
                width, height = 1280, 720

            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(filepath, fourcc, self.fps, (width, height))

            if not writer.isOpened():
                logger.error(f"Failed to create video writer: {filepath}")
                return

            # Write pre-event frames
            frames_written = 0
            for _, frame in pre_frames:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                
                # Add overlay text
                overlay_frame = frame.copy()
                cv2.putText(overlay_frame, f"[PRE-EVENT] {alert_type}",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                           (0, 255, 255), 2)
                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(overlay_frame, timestamp_str,
                           (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                           (255, 255, 255), 1)
                
                writer.write(overlay_frame)
                frames_written += 1

            logger.info(f"Wrote {frames_written} pre-event frames")

            # Record post-event frames
            post_frames_target = self.post_seconds * self.fps
            post_frames_written = 0
            frame_interval = 1.0 / self.fps
            
            start_time = time.time()
            while post_frames_written < post_frames_target:
                frame = self.camera.get_frame()
                if frame is not None:
                    if frame.shape[:2] != (height, width):
                        frame = cv2.resize(frame, (width, height))
                    
                    overlay_frame = frame.copy()
                    cv2.putText(overlay_frame, f"[RECORDING] {alert_type}",
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                               (0, 0, 255), 2)
                    elapsed = time.time() - start_time
                    cv2.putText(overlay_frame, f"Post-event: {elapsed:.1f}s / {self.post_seconds}s",
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                               (0, 0, 255), 1)
                    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(overlay_frame, timestamp_str,
                               (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                               (255, 255, 255), 1)
                    
                    writer.write(overlay_frame)
                    post_frames_written += 1

                time.sleep(frame_interval)

                # Safety timeout
                if time.time() - start_time > self.post_seconds + 5:
                    break

            writer.release()
            total_frames = frames_written + post_frames_written
            logger.info(
                f"Recording saved: {filepath} "
                f"({total_frames} frames, ~{total_frames/self.fps:.1f}s)"
            )

        except Exception as e:
            logger.error(f"Recording error: {e}")
        finally:
            with self._lock:
                self._recording = False

    def get_recordings(self):
        """List all recorded clips."""
        recordings = []
        if not os.path.exists(self.recordings_dir):
            return recordings
        
        for f in sorted(os.listdir(self.recordings_dir), reverse=True):
            if f.endswith('.mp4'):
                filepath = os.path.join(self.recordings_dir, f)
                stat = os.stat(filepath)
                recordings.append({
                    "filename": f,
                    "path": filepath,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })
        return recordings

    def is_recording(self):
        """Check if currently recording."""
        with self._lock:
            return self._recording
