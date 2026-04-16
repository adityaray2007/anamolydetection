# AI Sentinel - Project Overview & Defense Applications

## 1. Project Overview
**AI Sentinel** is an advanced, AI-powered surveillance system designed for real-time monitoring and anomaly detection. It seamlessly integrates traditional video surveillance with cutting-edge artificial intelligence, including facial recognition and Vision Language Models (VLMs), to autonomously detect intruders, hazards, and suspicious activities. 

The system provides a live web-based dashboard and records critical events automatically, serving as a comprehensive intelligent security solution.

## 2. Technical Details & Architecture
The project is built on a highly efficient, edge-compatible architecture designed to run locally, ensuring data privacy and fast response times.

### **Tech Stack**
- **Core Logic:** Python 3.12
- **Video Processing:** **OpenCV** captures live video feeds (e.g., via DroidCam WiFi) and maintains a rolling frame buffer for pre-event and post-event recording.
- **Face Recognition:** **InsightFace** provides GPU-accelerated face detection and recognition. It compares faces against a local database of known persons in real-time.
- **Vision Language Model (VLM):** **Ollama** running the **moondream** model (~1.6B parameters). This lightweight VLM analyzes frames periodically (or during motion bursts) to understand the context of the scene and detect hazards like fire, smoke, weapons, or break-ins.
- **Web Dashboard:** **Flask** serves a sleek, dark-themed responsive dashboard. It utilizes Server-Sent Events (SSE) to push real-time alerts to the front end.
- **Storage:** **SQLite** is used for logging alert history and metadata, while video clips (MP4) are stored directly on the filesystem.

### **System Workflow**
1. **Camera Feed:** Video is captured and stored in a continuous rolling buffer.
2. **Parallel Detection Engines:** 
   - *Face Engine:* Scans frames for unauthorized individuals.
   - *VLM Engine:* Analyzes the scene for complex hazards (e.g., "person holding a weapon" or "smoke in the hallway").
3. **Alerting & Recording:** When an anomaly is detected, an alert is pushed to the dashboard. The system extracts the rolling buffer (10s before the event) and continues recording (10s after) to save a complete clip of the incident.

## 3. Applications in Defense and Military
AI Sentinel's offline capabilities, lightweight footprint, and advanced analytic models make it highly suitable for various defense and military applications:

### **A. Perimeter & Base Security**
- **Automated Watchstanding:** AI Sentinel can monitor base perimeters 24/7 without fatigue. It can instantly recognize authorized personnel and flag unauthorized intruders or vehicles approaching secure zones.
- **Fence Line Monitoring:** The VLM can be prompted to detect specific vulnerabilities such as wire climbing, tampering, or object throwing over perimeters.

### **B. Tactical Edge Deployments**
- **Forward Operating Bases (FOBs):** Because the system runs entirely locally without relying on cloud infrastructure (using Ollama and InsightFace), it can be deployed in remote areas with zero internet connectivity.
- **Rapid Deployment:** The system is lightweight enough to run on ruggedized laptops equipped with entry-level GPUs, making it ideal for temporary checkpoints or highly mobile units.

### **C. Hazard & Sabotage Detection**
- **Early Warning System:** The VLM component acts as a continuously observing eye, capable of instantly detecting smoke, fire, or explosions before traditional sensors might trigger.
- **Weapon Detection:** The VLM can be fine-tuned or prompted to look specifically for long-arms, sidearms, or dropped packages/IEDs left behind by unknown individuals.

### **D. Post-Event Forensics and Intelligence Gathering**
- **Intelligent Archiving:** Unlike traditional CCTVs that record hours of empty footage, AI Sentinel's Event Recorder saves specific 20-second clips around an incident. This drastically reduces the time intelligence officers spend reviewing footage.
- **Actionable Alerts:** Real-time push notifications can be integrated into military command-and-control (C2) systems, providing immediate situational awareness to commanders.

## 4. Hardware Requirements for Edge Deployment
To ensure real-time responsiveness in a mission-critical defense scenario:
- **Processor:** Intel Core i7 (10th Gen+) or AMD equivalent.
- **Memory:** 16 GB+ RAM.
- **GPU:** Dedicated NVIDIA GPU (minimum 4GB VRAM, e.g., RTX 3050+) to accelerate the InsightFace and moondream VLM models for instant inference.
