/**
 * AI Sentinel — Dashboard Frontend
 * Handles SSE alerts, face management, recordings, and settings
 */

// ── State ──────────────────────────────────────────────
let alerts = [];
let eventSource = null;
let statusInterval = null;

// ── Initialize ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    connectSSE();
    loadAlerts();
    loadFaces();
    loadRecordings();
    startStatusPolling();
    updateTimestamp();
    setupRangeInput();
});

// ── SSE Connection ─────────────────────────────────────
function connectSSE() {
    if (eventSource) eventSource.close();
    
    eventSource = new EventSource('/api/events');
    
    eventSource.onmessage = (event) => {
        try {
            const alert = JSON.parse(event.data);
            handleNewAlert(alert);
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };
    
    eventSource.onerror = () => {
        console.warn('SSE connection lost, reconnecting...');
        setTimeout(connectSSE, 3000);
    };
    
    eventSource.onopen = () => {
        console.log('SSE connected');
    };
}

// ── Alert Handling ─────────────────────────────────────
function handleNewAlert(alert) {
    // Add to list
    addAlertToUI(alert, true);
    
    // Show toast
    showToast(alert.icon, alert.label, alert.description, alert.severity);
    
    // Play sound
    playAlertSound();
    
    // Update counters
    updateAlertCount();
    
    // Show recording indicator if applicable
    if (alert.recording_path) {
        const indicator = document.getElementById('recordingIndicator');
        indicator.style.display = 'flex';
        setTimeout(() => { indicator.style.display = 'none'; }, 20000);
    }
}

function addAlertToUI(alert, prepend = false) {
    const noAlerts = document.getElementById('noAlerts');
    if (noAlerts) noAlerts.style.display = 'none';
    
    const alertList = document.getElementById('alertList');
    const item = document.createElement('div');
    item.className = `alert-item ${alert.severity}`;
    item.id = `alert-${alert.id}`;
    
    let thumbHtml = '';
    if (alert.thumbnail) {
        thumbHtml = `<img src="data:image/jpeg;base64,${alert.thumbnail}" class="alert-thumb" alt="Alert thumbnail" />`;
    }
    
    const timeStr = alert.datetime || new Date(alert.timestamp * 1000).toLocaleTimeString();
    
    item.innerHTML = `
        <span class="alert-icon">${alert.icon || '⚠️'}</span>
        <div class="alert-content">
            <div class="alert-title">${alert.label || alert.alert_type}</div>
            <div class="alert-desc" title="${alert.description || ''}">${alert.description || ''}</div>
        </div>
        <span class="alert-time">${timeStr}</span>
        ${thumbHtml}
    `;
    
    item.onclick = () => acknowledgeAlert(alert.id);
    
    if (prepend) {
        alertList.insertBefore(item, alertList.firstChild);
    } else {
        alertList.appendChild(item);
    }
}

async function loadAlerts() {
    try {
        const resp = await fetch('/api/alerts');
        const data = await resp.json();
        
        const alertList = document.getElementById('alertList');
        const noAlerts = document.getElementById('noAlerts');
        
        if (data.alerts && data.alerts.length > 0) {
            noAlerts.style.display = 'none';
            // Clear existing (except empty state)
            alertList.querySelectorAll('.alert-item').forEach(el => el.remove());
            data.alerts.forEach(alert => addAlertToUI(alert));
        }
        
        updateAlertCount();
    } catch (e) {
        console.error('Failed to load alerts:', e);
    }
}

async function acknowledgeAlert(alertId) {
    try {
        await fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' });
        const item = document.getElementById(`alert-${alertId}`);
        if (item) {
            item.style.opacity = '0.5';
            item.style.borderColor = 'var(--border-subtle)';
            item.style.background = 'transparent';
        }
        updateAlertCount();
    } catch (e) {
        console.error('Failed to acknowledge alert:', e);
    }
}

async function clearAlerts() {
    if (!confirm('Clear all alerts?')) return;
    try {
        await fetch('/api/alerts/clear', { method: 'POST' });
        const alertList = document.getElementById('alertList');
        alertList.querySelectorAll('.alert-item').forEach(el => el.remove());
        document.getElementById('noAlerts').style.display = 'flex';
        updateAlertCount();
        showToast('✅', 'Cleared', 'All alerts have been cleared', 'success');
    } catch (e) {
        console.error('Failed to clear alerts:', e);
    }
}

function updateAlertCount() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(stats => {
            document.getElementById('alertCount').textContent = stats.unacknowledged || 0;
            const critChip = document.getElementById('criticalChip');
            if (stats.critical > 0) {
                critChip.style.display = 'flex';
                document.getElementById('criticalCount').textContent = stats.critical;
            } else {
                critChip.style.display = 'none';
            }
        })
        .catch(() => {});
}

// ── Face Management ────────────────────────────────────
async function loadFaces() {
    try {
        const resp = await fetch('/api/faces');
        const data = await resp.json();
        
        const faceList = document.getElementById('faceList');
        const noFaces = document.getElementById('noFaces');
        
        faceList.querySelectorAll('.face-item').forEach(el => el.remove());
        
        const people = data.faces || {};
        const names = Object.keys(people);
        
        document.getElementById('faceCount').textContent = names.length;
        
        if (names.length === 0) {
            noFaces.style.display = 'flex';
            return;
        }
        
        noFaces.style.display = 'none';
        
        names.forEach(name => {
            const count = people[name];
            const item = document.createElement('div');
            item.className = 'face-item';
            item.innerHTML = `
                <div class="face-avatar">${name.charAt(0).toUpperCase()}</div>
                <div class="face-info">
                    <div class="face-name">${name}</div>
                    <div class="face-count">${count} photo${count !== 1 ? 's' : ''}</div>
                </div>
                <button class="face-remove" onclick="removeFace('${name}')" title="Remove">🗑️</button>
            `;
            faceList.appendChild(item);
        });
    } catch (e) {
        console.error('Failed to load faces:', e);
    }
}

let liveCaptureCount = 0;

function showAddFaceModal() {
    document.getElementById('addFaceModal').style.display = 'flex';
    document.getElementById('personName').value = '';
    document.getElementById('faceImage').value = '';
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById('uploadPlaceholder').style.display = 'block';
    switchFaceTab('upload');
}

function hideAddFaceModal() {
    document.getElementById('addFaceModal').style.display = 'none';
    if (document.getElementById('miniVideoFeed')) {
        document.getElementById('miniVideoFeed').src = '';
    }
}

function switchFaceTab(mode) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    document.getElementById('addFaceBtn').style.display = mode === 'upload' ? 'block' : 'none';
    document.getElementById('doneLiveBtn').style.display = mode === 'live' ? 'block' : 'none';
    
    if (mode === 'upload') {
        document.getElementById('tabUploadBtn').classList.add('active');
        document.getElementById('tabUploadMode').classList.add('active');
        document.getElementById('miniVideoFeed').src = '';
    } else {
        document.getElementById('tabLiveBtn').classList.add('active');
        document.getElementById('tabLiveMode').classList.add('active');
        
        // Start live feed
        document.getElementById('miniVideoFeed').src = '/video_feed';
        
        // Reset counters
        liveCaptureCount = 0;
        document.getElementById('captureCount').textContent = '0';
        document.getElementById('captureBadge').style.display = 'none';
    }
}

async function captureLiveFace() {
    const name = document.getElementById('personName').value.trim();
    if (!name) { showToast('⚠️', 'Error', 'Please enter a name first', 'warning'); return; }
    
    const btn = document.getElementById('captureLiveBtn');
    btn.textContent = 'Capturing...';
    btn.disabled = true;
    
    try {
        const resp = await fetch('/api/faces/capture_live', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name })
        });
        const data = await resp.json();
        
        if (data.success) {
            liveCaptureCount++;
            const badge = document.getElementById('captureBadge');
            badge.style.display = 'inline-block';
            document.getElementById('captureCount').textContent = liveCaptureCount;
            
            // Pop animation
            badge.classList.remove('pop');
            void badge.offsetWidth; // trigger reflow
            badge.classList.add('pop');
            
            showToast('✅', 'Captured', `Frame ${liveCaptureCount} saved for ${name}`, 'success');
        } else {
            showToast('❌', 'Failed', data.message || 'No face found in frame', 'warning');
        }
    } catch (e) {
        showToast('❌', 'Error', 'Failed to capture frame', 'critical');
    } finally {
        btn.textContent = '📸 Capture Frame';
        btn.disabled = false;
    }
}

function previewImage(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const preview = document.getElementById('imagePreview');
            preview.src = e.target.result;
            preview.style.display = 'block';
            document.getElementById('uploadPlaceholder').style.display = 'none';
        };
        reader.readAsDataURL(input.files[0]);
    }
}

async function addFace() {
    const name = document.getElementById('personName').value.trim();
    const fileInput = document.getElementById('faceImage');
    
    if (!name) { showToast('⚠️', 'Error', 'Please enter a name', 'warning'); return; }
    if (!fileInput.files || !fileInput.files[0]) { showToast('⚠️', 'Error', 'Please select an image', 'warning'); return; }
    
    const btn = document.getElementById('addFaceBtn');
    btn.textContent = 'Registering...';
    btn.disabled = true;
    
    const formData = new FormData();
    formData.append('name', name);
    formData.append('image', fileInput.files[0]);
    
    try {
        const resp = await fetch('/api/faces/add', { method: 'POST', body: formData });
        const data = await resp.json();
        
        if (data.success) {
            showToast('✅', 'Registered', `Face registered for ${name}`, 'success');
            hideAddFaceModal();
            loadFaces();
        } else {
            showToast('❌', 'Failed', data.message || 'Failed to register face', 'critical');
        }
    } catch (e) {
        showToast('❌', 'Error', 'Failed to register face', 'critical');
    } finally {
        btn.textContent = 'Upload & Register';
        btn.disabled = false;
    }
}

async function removeFace(name) {
    if (!confirm(`Remove ${name} from the database?`)) return;
    
    try {
        const resp = await fetch(`/api/faces/${name}`, { method: 'DELETE' });
        const data = await resp.json();
        
        if (data.success) {
            showToast('✅', 'Removed', `${name} removed from database`, 'success');
            loadFaces();
        }
    } catch (e) {
        showToast('❌', 'Error', 'Failed to remove face', 'critical');
    }
}

// ── Recordings ─────────────────────────────────────────
async function loadRecordings() {
    try {
        const resp = await fetch('/api/recordings');
        const data = await resp.json();
        
        const list = document.getElementById('recordingList');
        const noRec = document.getElementById('noRecordings');
        
        list.querySelectorAll('.recording-item').forEach(el => el.remove());
        
        const recordings = data.recordings || [];
        
        if (recordings.length === 0) {
            noRec.style.display = 'flex';
            return;
        }
        
        noRec.style.display = 'none';
        
        recordings.forEach(rec => {
            const item = document.createElement('div');
            item.className = 'recording-item';
            item.innerHTML = `
                <span class="recording-icon">🎬</span>
                <div class="recording-info">
                    <div class="recording-name">${rec.filename}</div>
                    <div class="recording-meta">${rec.created} · ${rec.size_mb} MB</div>
                </div>
                <a href="/api/recordings/${rec.filename}" class="recording-download" download>⬇ Download</a>
            `;
            list.appendChild(item);
        });
    } catch (e) {
        console.error('Failed to load recordings:', e);
    }
}

function refreshRecordings() {
    loadRecordings();
    showToast('🔄', 'Refreshed', 'Recordings list updated', 'success');
}

// ── Status Polling ─────────────────────────────────────
function startStatusPolling() {
    updateStatus();
    statusInterval = setInterval(updateStatus, 5000);
}

async function updateStatus() {
    try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        
        // Camera status
        const camStatus = document.getElementById('cameraStatus');
        if (data.camera_connected) {
            camStatus.textContent = 'Connected';
            camStatus.style.color = '#34d399';
        } else {
            camStatus.textContent = 'Disconnected';
            camStatus.style.color = '#ef4444';
        }
        
        // VLM status
        const vlmStatus = document.getElementById('vlmEngineStatus');
        vlmStatus.textContent = data.vlm_available ? 'Online' : 'Offline';
        vlmStatus.className = `vlm-value ${data.vlm_available ? 'online' : 'offline'}`;
        
        // Face engine
        const faceStatus = document.getElementById('faceEngineStatus');
        faceStatus.textContent = data.face_engine_ready ? 'Online' : 'Offline';
        faceStatus.className = `vlm-value ${data.face_engine_ready ? 'online' : 'offline'}`;
        
        // Last analysis
        if (data.last_analysis) {
            document.getElementById('lastAnalysis').textContent = data.last_analysis;
        }
        
        // Scene status
        if (data.scene_status) {
            document.getElementById('sceneStatus').textContent = data.scene_status;
        }

        // Last face match confidence preview
        const facePreview = document.getElementById('faceMatchPreview');
        if (facePreview && data.last_face_name && data.last_face_name !== '—') {
            const label = data.last_face_known ? 'Known' : 'Unknown';
            const confidence = Number(data.last_face_confidence || 0).toFixed(2);
            const seen = data.last_face_seen ? ` @ ${data.last_face_seen}` : '';
            facePreview.textContent = `${data.last_face_name} (${label}, ${confidence})${seen}`;
            facePreview.className = `vlm-value ${data.last_face_known ? 'online' : 'offline'}`;
        } else if (facePreview) {
            facePreview.textContent = '—';
            facePreview.className = 'vlm-value';
        }
        
        // Update face count
        if (data.registered_faces !== undefined) {
            document.getElementById('faceCount').textContent = data.registered_faces;
        }
        
    } catch (e) {
        // Silent fail
    }
}

// ── Settings ───────────────────────────────────────────
function toggleSettings() {
    const overlay = document.getElementById('settingsOverlay');
    if (overlay.style.display === 'none' || !overlay.style.display) {
        overlay.style.display = 'block';
        loadSettings();
    } else {
        overlay.style.display = 'none';
    }
}

async function loadSettings() {
    try {
        const resp = await fetch('/api/settings');
        const data = await resp.json();
        
        if (data.camera_url) document.getElementById('cameraUrl').value = data.camera_url;
        if (data.face_threshold) {
            document.getElementById('faceThreshold').value = data.face_threshold;
            document.getElementById('thresholdValue').textContent = parseFloat(data.face_threshold).toFixed(2);
        }
        if (data.vlm_interval) document.getElementById('vlmInterval').value = data.vlm_interval;
        if (data.alert_cooldown) document.getElementById('alertCooldown').value = data.alert_cooldown;
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

async function saveSettings() {
    const settings = {
        camera_url: document.getElementById('cameraUrl').value,
        face_threshold: parseFloat(document.getElementById('faceThreshold').value),
        vlm_interval: parseInt(document.getElementById('vlmInterval').value),
        alert_cooldown: parseInt(document.getElementById('alertCooldown').value),
    };
    
    try {
        const resp = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        const data = await resp.json();
        
        if (data.success) {
            showToast('✅', 'Saved', 'Settings updated successfully', 'success');
            toggleSettings();
        } else {
            showToast('❌', 'Error', data.message || 'Failed to save settings', 'critical');
        }
    } catch (e) {
        showToast('❌', 'Error', 'Failed to save settings', 'critical');
    }
}

function setupRangeInput() {
    const range = document.getElementById('faceThreshold');
    const value = document.getElementById('thresholdValue');
    if (range && value) {
        range.addEventListener('input', () => {
            value.textContent = parseFloat(range.value).toFixed(2);
        });
    }
}

// ── Fullscreen ─────────────────────────────────────────
function toggleFullscreen() {
    const panel = document.getElementById('feedPanel');
    panel.classList.toggle('fullscreen');
}

// ── Switch Camera ──────────────────────────────────────
async function toggleCamera() {
    try {
        const resp = await fetch('/api/settings');
        const data = await resp.json();
        
        let targetUrl = "0";
        if (data.camera_url === "0" || data.camera_url === 0) {
            // Need to ask for DroidCam URL if not set
            const droidCamUrl = prompt("Enter DroidCam URL (e.g. http://192.168.1.100:4747/video):", "http://192.168.1.100:4747/video");
            if (!droidCamUrl) return;
            targetUrl = droidCamUrl;
        }
        
        // Update setting
        const settings = { camera_url: targetUrl };
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        
        showToast('🔄', 'Camera Switched', `Switched to ${targetUrl === '0' ? 'System Camera' : 'DroidCam'}`, 'info');
        
        // Update button text
        const btn = document.getElementById('cameraToggleBtn');
        if (btn) {
            btn.innerHTML = targetUrl === '0' ? '📱 DroidCam' : '💻 PC Cam';
        }
        
        // Reload settings panel if open
        const cameraUrlInput = document.getElementById('cameraUrl');
        if (cameraUrlInput) cameraUrlInput.value = targetUrl;
        
    } catch (e) {
        showToast('❌', 'Error', 'Failed to switch camera', 'critical');
    }
}

// ── Toast Notifications ────────────────────────────────
function showToast(icon, title, desc, severity = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${severity}`;
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-desc">${desc}</div>
        </div>
    `;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastIn 0.3s ease reverse forwards';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// ── Utility ────────────────────────────────────────────
function playAlertSound() {
    try {
        const audio = document.getElementById('alertSound');
        if (audio) {
            audio.currentTime = 0;
            audio.play().catch(() => {});
        }
    } catch (e) {}
}

function updateTimestamp() {
    const el = document.getElementById('feedTimestamp');
    if (el) {
        setInterval(() => {
            el.textContent = new Date().toLocaleTimeString();
        }, 1000);
    }
}

// Close modals/settings on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideAddFaceModal();
        const settings = document.getElementById('settingsOverlay');
        if (settings.style.display !== 'none') {
            settings.style.display = 'none';
        }
        const feedPanel = document.getElementById('feedPanel');
        if (feedPanel.classList.contains('fullscreen')) {
            feedPanel.classList.remove('fullscreen');
        }
    }
});

// Click outside modal to close
document.getElementById('addFaceModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'addFaceModal') hideAddFaceModal();
});

document.getElementById('settingsOverlay')?.addEventListener('click', (e) => {
    if (e.target.id === 'settingsOverlay') toggleSettings();
});
