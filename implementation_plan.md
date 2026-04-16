# AI Surveillance System - Implementation Plan

## Overview
Build an AI-powered surveillance system that:
1. Monitors a live DroidCam WiFi camera feed
2. Detects and recognizes faces against a local database of known people
3. Alerts on unrecognized faces (intruder detection)
4. Uses a Vision Language Model (VLM) to detect hazardous activities (smoke/fire, break-ins, emergencies)
5. Records 10-second clips before and after detected events
6. Provides a sleek web-based dashboard for monitoring, alerts, and face management

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  DroidCam   │────▶│  Video Pipeline  │────▶│  Web Dashboard   │
│  (WiFi)     │     │  (OpenCV)        │     │  (Flask + SSE)   │
└─────────────┘     └──────┬───────────┘     └─────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
              ┌─────▼─────┐ ┌────▼──────┐
              │   Face     │ │   VLM     │
              │ Recognition│ │  Analysis │
              │ (InsightFace)│ │(Ollama + │
              │            │ │ MiniCPM-V)│
              └─────┬──────┘ └────┬──────┘
                    │             │
              ┌─────▼─────────────▼─────┐
              │    Alert Manager        │
              │  + Event Recorder       │
              └─────────────────────────┘
```

## Tech Stack
- **Python 3.12** with `uv` virtual environment
- **OpenCV** - Video capture and frame processing
- **InsightFace** - Face detection and recognition (lightweight, GPU-accelerated)
- **Ollama + moondream** - Lightweight VLM for scene analysis (~1.6B params, fast inference)
- **Flask** - Web server with Server-Sent Events (SSE) for real-time updates
- **SQLite** - Alert history storage

## Project Structure

```
ai-surveillance/
├── app.py                  # Main Flask application & entry point
├── config.py               # Configuration settings
├── requirements.txt        # Python dependencies
├── known_faces/            # Face database (folder per person)
│   └── example_person/     # Drop photos here
├── recordings/             # Event recordings saved here
├── database/               # SQLite database
├── core/
│   ├── __init__.py
│   ├── camera.py           # DroidCam video capture & frame buffer
│   ├── face_engine.py      # Face detection & recognition (InsightFace)
│   ├── vlm_engine.py       # VLM-based hazard detection (Ollama)
│   ├── alert_manager.py    # Alert creation, storage, notification
│   └── recorder.py         # Event clip recording (10s before + after)
├── static/
│   ├── css/
│   │   └── style.css       # Dashboard styling
│   └── js/
│       └── app.js          # Frontend JavaScript
└── templates/
    └── index.html          # Dashboard HTML template
```

## Proposed Changes

### Core Module

#### [NEW] config.py
Global configuration: camera URL, detection intervals, thresholds, paths.

#### [NEW] core/camera.py
- DroidCam WiFi video capture via OpenCV
- Rolling frame buffer (stores last 10 seconds of frames)
- Thread-safe frame access for multiple consumers

#### [NEW] core/face_engine.py
- InsightFace-based face detection and embedding
- Auto-loads known faces from `known_faces/` directory
- Watches for new faces added to the directory
- Returns match/no-match with confidence scores

#### [NEW] core/vlm_engine.py
- Ollama integration with moondream vision model
- Periodic frame analysis for hazard detection
- Structured prompt for detecting: smoke, fire, break-ins, weapons, injuries, etc.

#### [NEW] core/alert_manager.py
- SQLite-backed alert storage
- Alert creation with metadata (type, timestamp, frame, description)
- SSE broadcast to connected web clients

#### [NEW] core/recorder.py
- Uses camera's rolling buffer to save pre-event frames
- Continues recording post-event frames
- Saves as MP4 clips in `recordings/`

### Web Dashboard

#### [NEW] app.py
- Flask application with routes for:
  - Live video feed (MJPEG stream)
  - SSE endpoint for real-time alerts
  - Alert history API
  - Face management (upload/delete)
  - Settings configuration

#### [NEW] templates/index.html
- Dark-themed, premium dashboard layout
- Live camera feed panel
- Real-time alert notifications
- Alert history with thumbnails
- Face database management panel

#### [NEW] static/css/style.css
- Modern dark theme with glassmorphism
- Smooth animations and transitions
- Responsive layout

#### [NEW] static/js/app.js
- SSE client for real-time alert updates
- Face management UI interactions
- Alert history display

## Verification Plan

### Automated Tests
- Start the Flask server and verify all routes respond
- Test face enrollment and recognition pipeline
- Test VLM analysis returns structured output

### Manual Verification
- Connect DroidCam and verify live feed displays in dashboard
- Add known faces and verify recognition
- Test alert generation and recording
