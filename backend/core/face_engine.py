"""
Face Recognition Engine - Uses InsightFace for detection and recognition.
Auto-loads known faces from directory and watches for new additions.
"""
import os
import cv2
import time
import threading
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FaceEngine:
    """Face detection and recognition engine using InsightFace."""

    def __init__(self, known_faces_dir, threshold=0.4, poll_interval=5):
        self.known_faces_dir = known_faces_dir
        self.threshold = threshold
        self.poll_interval = poll_interval

        # Known face data: {name: [embedding1, embedding2, ...]}
        self.known_faces = {}
        self._file_hashes = {}  # Track loaded files to detect new ones

        self._model = None
        self._lock = threading.Lock()
        self._watcher_running = False
        self._watcher_thread = None

    @staticmethod
    def _normalize_embedding(embedding):
        """Return L2-normalized embedding (or None if invalid)."""
        emb = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm <= 1e-8:
            return None
        return emb / norm

    @staticmethod
    def _pick_primary_face(faces):
        """Pick the largest detected face for stable registration."""
        if not faces:
            return None
        return max(
            faces,
            key=lambda f: float((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        )

    def initialize(self):
        """Initialize the InsightFace model."""
        try:
            try:
                from insightface.app import FaceAnalysis
            except ImportError:
                logger.error("InsightFace module not found. Please ensure you are running in the correct virtual environment (e.g., .\.venv311\Scripts\python.exe app.py)")
                return False
            
            logger.info("Initializing InsightFace model...")
            
            # Explicitly try CPU first if user has reported issues with CUDA DLLs
            # Or use a very safe fallback mechanism
            try:
                self._model = FaceAnalysis(
                    name="buffalo_s",
                    providers=["CPUExecutionProvider"] # Force CPU for maximum compatibility
                )
                self._model.prepare(ctx_id=0, det_size=(640, 640))
            except Exception as e:
                logger.warning(f"CPU initialization failed, trying default providers: {e}")
                self._model = FaceAnalysis(name="buffalo_s")
                self._model.prepare(ctx_id=0, det_size=(640, 640))

            logger.info("InsightFace model initialized successfully (Running on CPU)")
            
            # Load known faces
            self._load_known_faces()
            
            # Start directory watcher
            self._start_watcher()
            
            return True
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")
            return False

    def _load_known_faces(self):
        """Load all known faces from the directory structure."""
        if not os.path.exists(self.known_faces_dir):
            os.makedirs(self.known_faces_dir, exist_ok=True)
            logger.info(f"Created known faces directory: {self.known_faces_dir}")
            return

        loaded_count = 0
        for person_name in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, person_name)
            if not os.path.isdir(person_dir):
                continue

            for img_file in os.listdir(person_dir):
                img_path = os.path.join(person_dir, img_file)
                if not img_file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
                    continue

                file_key = img_path
                file_mtime = os.path.getmtime(img_path)

                # Skip already loaded files
                if file_key in self._file_hashes and self._file_hashes[file_key] == file_mtime:
                    continue

                try:
                    img = cv2.imread(img_path)
                    if img is None:
                        logger.warning(f"Could not read image: {img_path}")
                        continue

                    faces = self._model.get(img)
                    if len(faces) == 0:
                        logger.warning(f"No face found in: {img_path}")
                        continue

                    face = self._pick_primary_face(faces)
                    embedding = self._normalize_embedding(face.embedding)
                    if embedding is None:
                        logger.warning(f"Invalid face embedding in: {img_path}")
                        continue

                    with self._lock:
                        if person_name not in self.known_faces:
                            self.known_faces[person_name] = []
                        self.known_faces[person_name].append(embedding)
                        self._file_hashes[file_key] = file_mtime

                    loaded_count += 1
                    logger.info(f"Loaded face for '{person_name}' from {img_file}")

                except Exception as e:
                    logger.error(f"Error loading face from {img_path}: {e}")

        logger.info(f"Loaded {loaded_count} face(s) for {len(self.known_faces)} person(s)")

    def _start_watcher(self):
        """Start background thread to watch for new faces."""
        self._watcher_running = True
        self._watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watcher_thread.start()

    def _watch_loop(self):
        """Periodically check for new face images."""
        while self._watcher_running:
            time.sleep(self.poll_interval)
            try:
                self._load_known_faces()
            except Exception as e:
                logger.error(f"Face watcher error: {e}")

    def detect_and_recognize(self, frame):
        """
        Detect faces in frame and match against known faces.
        
        Returns list of dicts:
        [{"name": str, "confidence": float, "bbox": [x1,y1,x2,y2], "known": bool}, ...]
        """
        if self._model is None:
            return []

        try:
            faces = self._model.get(frame)
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []

        results = []
        for face in faces:
            bbox = face.bbox.astype(int).tolist()
            embedding = self._normalize_embedding(face.embedding)
            if embedding is None:
                continue

            best_match = None
            best_score = 0.0

            with self._lock:
                for name, embeddings in self.known_faces.items():
                    for known_emb in embeddings:
                        # Cosine similarity for unit-normalized vectors.
                        score = float(np.dot(embedding, known_emb))
                        if score > best_score:
                            best_score = score
                            best_match = name

            is_known = best_score >= self.threshold
            results.append({
                "name": best_match if is_known else "Unknown",
                "confidence": float(best_score),
                "bbox": bbox,
                "known": is_known,
            })

        return results

    def get_known_people(self):
        """Get list of registered people and their photo counts."""
        with self._lock:
            return {
                name: len(embeddings)
                for name, embeddings in self.known_faces.items()
            }

    def add_face(self, person_name, image_data):
        """
        Add a new face from uploaded image data.
        Returns (success, message).
        """
        person_dir = os.path.join(self.known_faces_dir, person_name)
        os.makedirs(person_dir, exist_ok=True)

        # Save the image
        timestamp = int(time.time())
        filename = f"{person_name}_{timestamp}.jpg"
        filepath = os.path.join(person_dir, filename)

        try:
            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return False, "Invalid image data"

            # Verify face is detectable
            faces = self._model.get(img)
            if len(faces) == 0:
                return False, "No face detected in the image"

            # Save image
            cv2.imwrite(filepath, img)

            # Register primary face embedding from the image.
            primary_face = self._pick_primary_face(faces)
            embedding = self._normalize_embedding(primary_face.embedding)
            if embedding is None:
                return False, "Invalid face embedding, try another image"

            with self._lock:
                if person_name not in self.known_faces:
                    self.known_faces[person_name] = []
                self.known_faces[person_name].append(embedding)
                self._file_hashes[filepath] = os.path.getmtime(filepath)

            logger.info(f"Added face for '{person_name}': {filename}")
            return True, f"Face registered for {person_name}"

        except Exception as e:
            logger.error(f"Error adding face: {e}")
            return False, str(e)

    def remove_person(self, person_name):
        """Remove a person and all their face data."""
        import shutil
        person_dir = os.path.join(self.known_faces_dir, person_name)

        with self._lock:
            if person_name in self.known_faces:
                del self.known_faces[person_name]

            # Remove file hashes for this person
            keys_to_remove = [k for k in self._file_hashes if person_name in k]
            for k in keys_to_remove:
                del self._file_hashes[k]

        if os.path.exists(person_dir):
            shutil.rmtree(person_dir)

        logger.info(f"Removed person: {person_name}")
        return True

    def stop(self):
        """Stop the face engine."""
        self._watcher_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5)
