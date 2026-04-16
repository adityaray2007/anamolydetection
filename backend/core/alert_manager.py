"""
Alert Manager - Handles alert creation, storage, and broadcasting.
"""
import os
import cv2
import time
import json
import sqlite3
import threading
import logging
import base64
import numpy as np
from datetime import datetime
from queue import Queue

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alerts with SQLite storage and SSE broadcasting."""

    ALERT_TYPES = {
        "UNKNOWN_FACE": {"severity": "warning", "icon": "👤", "label": "Unknown Person"},
        "FIRE": {"severity": "critical", "icon": "🔥", "label": "Fire Detected"},
        "SMOKE": {"severity": "critical", "icon": "💨", "label": "Smoke Detected"},
        "INTRUSION": {"severity": "critical", "icon": "🚨", "label": "Intrusion Detected"},
        "VIOLENCE": {"severity": "critical", "icon": "⚠️", "label": "Violence Detected"},
        "WEAPON": {"severity": "critical", "icon": "🔫", "label": "Weapon Detected"},
        "FALLEN_PERSON": {"severity": "warning", "icon": "🆘", "label": "Person Down"},
        "SUSPICIOUS": {"severity": "warning", "icon": "🔍", "label": "Suspicious Activity"},
    }

    def __init__(self, db_path, cooldown=30):
        self.db_path = db_path
        self.cooldown = cooldown
        self._last_alerts = {}  # {type: timestamp} for cooldown
        self._subscribers = []  # SSE subscriber queues
        self._lock = threading.Lock()
        
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                thumbnail TEXT,
                recording_path TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp 
            ON alerts(timestamp DESC)
        """)
        conn.commit()
        conn.close()
        logger.info(f"Alert database initialized: {self.db_path}")

    def create_alert(self, alert_type, description, frame=None, recording_path=None):
        """
        Create a new alert if not in cooldown period.
        Returns alert dict if created, None if suppressed.
        """
        now = time.time()

        # Check cooldown
        if alert_type in self._last_alerts:
            elapsed = now - self._last_alerts[alert_type]
            if elapsed < self.cooldown:
                logger.debug(f"Alert {alert_type} suppressed (cooldown: {self.cooldown - elapsed:.0f}s remaining)")
                return None

        self._last_alerts[alert_type] = now

        # Create thumbnail from frame
        thumbnail_b64 = None
        if frame is not None:
            try:
                thumb = cv2.resize(frame, (320, 240))
                _, buffer = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
                thumbnail_b64 = base64.b64encode(buffer).decode('utf-8')
            except Exception as e:
                logger.error(f"Error creating thumbnail: {e}")

        alert_info = self.ALERT_TYPES.get(alert_type, {
            "severity": "info", "icon": "ℹ️", "label": alert_type
        })

        alert = {
            "timestamp": now,
            "datetime": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
            "alert_type": alert_type,
            "severity": alert_info["severity"],
            "icon": alert_info["icon"],
            "label": alert_info["label"],
            "description": description,
            "thumbnail": thumbnail_b64,
            "recording_path": recording_path,
            "acknowledged": False,
        }

        # Store in database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """INSERT INTO alerts (timestamp, alert_type, severity, description, thumbnail, recording_path)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (now, alert_type, alert_info["severity"], description, thumbnail_b64, recording_path)
            )
            alert["id"] = cursor.lastrowid
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database error: {e}")
            alert["id"] = int(now * 1000)

        # Broadcast to SSE subscribers
        self._broadcast(alert)

        logger.warning(f"ALERT [{alert_type}]: {description}")
        return alert

    def _broadcast(self, alert):
        """Send alert to all SSE subscribers."""
        # Create a serializable copy (without binary thumbnail for SSE)
        sse_alert = {k: v for k, v in alert.items()}
        if sse_alert.get("thumbnail"):
            sse_alert["has_thumbnail"] = True
        
        message = json.dumps(sse_alert)
        
        with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(message)
                except:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def subscribe(self):
        """Subscribe to alert events. Returns a Queue."""
        q = Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        """Unsubscribe from alert events."""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def get_alerts(self, limit=50, offset=0):
        """Get recent alerts from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT id, timestamp, alert_type, severity, description, 
                          thumbnail, recording_path, acknowledged, created_at
                   FROM alerts ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            )
            alerts = []
            for row in cursor:
                alert_info = self.ALERT_TYPES.get(row["alert_type"], {
                    "severity": "info", "icon": "ℹ️", "label": row["alert_type"]
                })
                alerts.append({
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "datetime": datetime.fromtimestamp(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "alert_type": row["alert_type"],
                    "severity": row["severity"],
                    "icon": alert_info["icon"],
                    "label": alert_info["label"],
                    "description": row["description"],
                    "thumbnail": row["thumbnail"],
                    "has_thumbnail": row["thumbnail"] is not None,
                    "recording_path": row["recording_path"],
                    "acknowledged": bool(row["acknowledged"]),
                })
            conn.close()
            return alerts
        except Exception as e:
            logger.error(f"Error fetching alerts: {e}")
            return []

    def acknowledge_alert(self, alert_id):
        """Mark an alert as acknowledged."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False

    def clear_alerts(self):
        """Clear all alerts."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM alerts")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error clearing alerts: {e}")
            return False

    def get_stats(self):
        """Get alert statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            unack = conn.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0").fetchone()[0]
            critical = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE severity = 'critical' AND acknowledged = 0"
            ).fetchone()[0]
            conn.close()
            return {"total": total, "unacknowledged": unack, "critical": critical}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"total": 0, "unacknowledged": 0, "critical": 0}
