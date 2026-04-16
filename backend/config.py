"""
AI Surveillance System - Configuration
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Camera Settings ──────────────────────────────────────────────
# System Webcam (0) or DroidCam URL (e.g., "http://192.168.1.10:4747/video")
CAMERA_URL = os.environ.get("CAMERA_URL", "0")
# To use DroidCam, set CAMERA_URL to "http://10.12.76.200:4747/video"
# CAMERA_URL = "http://10.12.76.200:4747/video" 
CAMERA_FALLBACK = 0  # Fallback to system webcam if DroidCam fails
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FPS = 30

# ── Face Recognition Settings ───────────────────────────────────
KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")
FACE_RECOGNITION_THRESHOLD = 0.20  # Higher values are stricter; lower values are more permissive.
FACE_DETECTION_INTERVAL = 0.5  # Seconds between face detection runs
FACE_DB_POLL_INTERVAL = 5  # Seconds between checking for new faces in directory

# ── VLM Settings ─────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
VLM_MODEL = os.environ.get("VLM_MODEL", "moondream")  # Lightweight vision model
VLM_ANALYSIS_INTERVAL = 1  # Baseline seconds between VLM analyses
VLM_BURST_INTERVAL = 0.6  # Faster temporary interval during sudden motion/activity
VLM_MOTION_THRESHOLD = 999.0  # Mean grayscale-delta threshold to trigger burst mode
VLM_PROMPT = (
    "You are a CCTV safety monitor. "
    "Prioritize detecting short dangerous events: fighting, punching, kicking, grabbing, assault, "
    "weapon handling, fire, smoke, intrusion, or person collapsing. "
    "If you see possible violence, say it explicitly in one concise sentence."
)

# ── Alert Settings ───────────────────────────────────────────────
ALERT_COOLDOWN = 30  # Seconds before same type of alert can trigger again
DATABASE_PATH = os.path.join(BASE_DIR, "database", "alerts.db")

# ── Recording Settings ──────────────────────────────────────────
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
BUFFER_SECONDS = 10  # Seconds of pre-event footage to keep
POST_EVENT_SECONDS = 10  # Seconds of post-event footage to record
RECORDING_FPS = 15

# ── Web Dashboard ────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 5001
SECRET_KEY = os.environ.get("SECRET_KEY", "ai-surveillance-secret-key-change-me")

# ── Create directories ──────────────────────────────────────────
for d in [KNOWN_FACES_DIR, RECORDINGS_DIR, os.path.join(BASE_DIR, "database")]:
    os.makedirs(d, exist_ok=True)
