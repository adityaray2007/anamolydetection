"""
AI Sentinel — Main Application
Flask-based surveillance dashboard with face recognition and VLM hazard detection.
"""
import os
import cv2
import sys
import time
import json
import threading
import logging
from datetime import datetime
from flask import Flask, render_template, Response, request, jsonify, send_from_directory
import numpy as np

import config
from core.camera import Camera
from core.face_engine import FaceEngine
from core.vlm_engine import VLMEngine
from core.alert_manager import AlertManager
from core.recorder import EventRecorder

# ── Logging Setup ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(config.BASE_DIR, 'surveillance.log'))
    ]
)
logger = logging.getLogger(__name__)

# ── Flask App ───────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ── Initialize Components ──────────────────────────────
camera = Camera(
    source=config.CAMERA_URL,
    buffer_seconds=config.BUFFER_SECONDS,
    fps=config.RECORDING_FPS,
    width=config.FRAME_WIDTH,
    height=config.FRAME_HEIGHT,
)

face_engine = FaceEngine(
    known_faces_dir=config.KNOWN_FACES_DIR,
    threshold=config.FACE_RECOGNITION_THRESHOLD,
    poll_interval=config.FACE_DB_POLL_INTERVAL,
)

vlm_engine = VLMEngine(
    ollama_url=config.OLLAMA_BASE_URL,
    model=config.VLM_MODEL,
    prompt=config.VLM_PROMPT,
)

alert_manager = AlertManager(
    db_path=config.DATABASE_PATH,
    cooldown=config.ALERT_COOLDOWN,
)

recorder = EventRecorder(
    recordings_dir=config.RECORDINGS_DIR,
    camera=camera,
    pre_seconds=config.BUFFER_SECONDS,
    post_seconds=config.POST_EVENT_SECONDS,
    fps=config.RECORDING_FPS,
)

# ── Global State ────────────────────────────────────────
app_state = {
    "face_engine_ready": False,
    "vlm_available": False,
    "last_analysis": "—",
    "scene_status": "Initializing...",
    "last_vlm_time": 0,
    "last_face_time": 0,
    "last_face_name": "—",
    "last_face_confidence": 0.0,
    "last_face_known": False,
    "last_face_seen": "—",
}


# ════════════════════════════════════════════════════════
# Web Routes
# ════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    """MJPEG stream endpoint."""
    def generate():
        while True:
            frame_bytes = camera.get_jpeg_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(1.0 / 15)  # ~15 FPS for the stream

    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/events')
def sse_events():
    """Server-Sent Events endpoint for real-time alerts."""
    def stream():
        q = alert_manager.subscribe()
        try:
            while True:
                try:
                    message = q.get(timeout=30)
                    yield f"data: {message}\n\n"
                except:
                    yield f": keepalive\n\n"
        except GeneratorExit:
            alert_manager.unsubscribe(q)

    return Response(
        stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/api/alerts')
def get_alerts():
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    alerts = alert_manager.get_alerts(limit=limit, offset=offset)
    return jsonify({"alerts": alerts})


@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    success = alert_manager.acknowledge_alert(alert_id)
    return jsonify({"success": success})


@app.route('/api/alerts/clear', methods=['POST'])
def clear_alerts():
    success = alert_manager.clear_alerts()
    return jsonify({"success": success})


@app.route('/api/stats')
def get_stats():
    return jsonify(alert_manager.get_stats())


@app.route('/api/faces')
def get_faces():
    return jsonify({"faces": face_engine.get_known_people()})


@app.route('/api/faces/add', methods=['POST'])
def add_face():
    name = request.form.get('name', '').strip()
    image = request.files.get('image')

    if not name:
        return jsonify({"success": False, "message": "Name is required"})
    if not image:
        return jsonify({"success": False, "message": "Image is required"})

    image_data = image.read()
    success, message = face_engine.add_face(name, image_data)
    return jsonify({"success": success, "message": message})


@app.route('/api/faces/capture_live', methods=['POST'])
def capture_live_face():
    data = request.get_json() or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({"success": False, "message": "Name is required"})

    frame = camera.get_frame()
    if frame is None:
        return jsonify({"success": False, "message": "Camera is currently unavailable"})

    # encode the OpenCV frame to jpeg bytes
    import cv2
    raw_success, buffer = cv2.imencode('.jpg', frame)
    if not raw_success:
        return jsonify({"success": False, "message": "Failed to encode frame"})

    image_data = buffer.tobytes()
    success, message = face_engine.add_face(name, image_data)
    return jsonify({"success": success, "message": message})


@app.route('/api/faces/<name>', methods=['DELETE'])
def remove_face(name):
    success = face_engine.remove_person(name)
    return jsonify({"success": success})


@app.route('/api/recordings')
def get_recordings():
    return jsonify({"recordings": recorder.get_recordings()})


@app.route('/api/recordings/<filename>')
def download_recording(filename):
    return send_from_directory(config.RECORDINGS_DIR, filename, as_attachment=True)


@app.route('/api/status')
def get_status():
    return jsonify({
        "camera_connected": camera.is_connected(),
        "vlm_available": app_state["vlm_available"],
        "face_engine_ready": app_state["face_engine_ready"],
        "last_analysis": app_state["last_analysis"],
        "scene_status": app_state["scene_status"],
        "registered_faces": len(face_engine.get_known_people()),
        "recording": recorder.is_recording(),
        "last_face_name": app_state["last_face_name"],
        "last_face_confidence": app_state["last_face_confidence"],
        "last_face_known": app_state["last_face_known"],
        "last_face_seen": app_state["last_face_seen"],
    })


@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({
        "camera_url": config.CAMERA_URL,
        "face_threshold": config.FACE_RECOGNITION_THRESHOLD,
        "vlm_interval": config.VLM_ANALYSIS_INTERVAL,
        "alert_cooldown": config.ALERT_COOLDOWN,
    })


@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    
    if 'camera_url' in data:
        config.CAMERA_URL = data['camera_url']
        # Reconnect camera with new URL
        camera.source = data['camera_url']
        camera._connected = False
    
    if 'face_threshold' in data:
        requested_threshold = float(data['face_threshold'])
        # Keep threshold within a stable recognition range.
        clamped_threshold = max(0.10, min(0.60, requested_threshold))
        config.FACE_RECOGNITION_THRESHOLD = clamped_threshold
        face_engine.threshold = clamped_threshold
    
    if 'vlm_interval' in data:
        config.VLM_ANALYSIS_INTERVAL = int(data['vlm_interval'])
    
    if 'alert_cooldown' in data:
        config.ALERT_COOLDOWN = int(data['alert_cooldown'])
        alert_manager.cooldown = int(data['alert_cooldown'])
    
    return jsonify({"success": True, "message": "Settings updated"})


# ════════════════════════════════════════════════════════
# Background Analysis Loops
# ════════════════════════════════════════════════════════

def face_detection_loop():
    """Background thread for face detection and recognition."""
    logger.info("Face detection loop started")
    
    while True:
        try:
            if not app_state["face_engine_ready"]:
                time.sleep(1)
                continue

            frame = camera.get_frame()
            if frame is None:
                time.sleep(0.5)
                continue

            results = face_engine.detect_and_recognize(frame)
            if results:
                # Show strongest current face match in UI.
                top_face = max(results, key=lambda f: f.get("confidence", 0.0))
                app_state["last_face_name"] = top_face.get("name", "Unknown")
                app_state["last_face_confidence"] = float(top_face.get("confidence", 0.0))
                app_state["last_face_known"] = bool(top_face.get("known", False))
                app_state["last_face_seen"] = datetime.now().strftime("%H:%M:%S")
            else:
                # Clear the UI if nobody is in the frame
                app_state["last_face_name"] = "No face detected"
                app_state["last_face_confidence"] = 0.0
                app_state["last_face_known"] = False
                app_state["last_face_seen"] = "-"

            for face in results:
                if not face["known"]:
                    # Unknown face detected!
                    desc = f"Unregistered person detected (confidence: {face['confidence']:.2f})"
                    
                    # Draw bbox on frame for thumbnail
                    x1, y1, x2, y2 = face["bbox"]
                    thumb_frame = frame.copy()
                    cv2.rectangle(thumb_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(thumb_frame, "UNKNOWN", (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                    # Record event
                    rec_path = recorder.record_event("UNKNOWN_FACE", desc)
                    
                    alert_manager.create_alert(
                        alert_type="UNKNOWN_FACE",
                        description=desc,
                        frame=thumb_frame,
                        recording_path=rec_path,
                    )

            time.sleep(config.FACE_DETECTION_INTERVAL)

        except Exception as e:
            logger.error(f"Face detection error: {e}")
            time.sleep(2)


def vlm_analysis_loop():
    """Background thread for VLM-based hazard detection."""
    logger.info("VLM analysis loop started")
    prev_gray = None
    burst_until = 0.0

    while True:
        try:
            if not app_state["vlm_available"]:
                time.sleep(5)
                continue

            frame = camera.get_frame()
            if frame is None:
                time.sleep(1)
                continue

            # Analyze frame unconditionally unconditionally without motion check
            result = vlm_engine.analyze_frame(frame)
            
            app_state["last_analysis"] = datetime.now().strftime("%H:%M:%S")
            app_state["scene_status"] = result.get("description", "Normal")[:60]

            if result.get("alert", False):
                alert_type = result.get("type", "SUSPICIOUS")
                desc = result.get("description", "Hazardous activity detected")
                
                # Record event
                rec_path = recorder.record_event(alert_type, desc)
                
                alert_manager.create_alert(
                    alert_type=alert_type,
                    description=desc,
                    frame=frame,
                    recording_path=rec_path,
                )

            time.sleep(config.VLM_ANALYSIS_INTERVAL)

        except Exception as e:
            logger.error(f"VLM analysis error: {e}")
            time.sleep(5)


def initialize_engines():
    """Initialize face and VLM engines in background."""
    # Initialize face engine
    logger.info("Initializing face recognition engine...")
    if face_engine.initialize():
        app_state["face_engine_ready"] = True
        logger.info("[SUCCESS] Face recognition engine ready")
    else:
        logger.warning("Face recognition engine failed to initialize")

    # Initialize VLM engine
    logger.info("Initializing VLM engine...")
    if vlm_engine.initialize():
        app_state["vlm_available"] = True
        logger.info("[SUCCESS] VLM engine ready")
    else:
        logger.warning("VLM engine not available (start Ollama and pull moondream model)")


# ════════════════════════════════════════════════════════
# Startup
# ════════════════════════════════════════════════════════

def start_background_services():
    """Start all background threads."""
    # Start camera
    camera.start()
    
    # Initialize engines in background
    init_thread = threading.Thread(target=initialize_engines, daemon=True)
    init_thread.start()
    
    # Start analysis loops
    face_thread = threading.Thread(target=face_detection_loop, daemon=True)
    face_thread.start()
    
    vlm_thread = threading.Thread(target=vlm_analysis_loop, daemon=True)
    vlm_thread.start()
    
    logger.info("All background services started")


if __name__ == '__main__':
    print("""
    +-----------------------------------------------+
    |         AI SENTINEL v1.0                      |
    |         AI Surveillance System                |
    +-----------------------------------------------+
    |  Dashboard: http://localhost:5001             |
    |  VLM:       Ollama + moondream                |
    +-----------------------------------------------+
    """)
    
    start_background_services()
    
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
