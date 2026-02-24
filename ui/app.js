// ===== DOM Elements =====
const recordBtn = document.getElementById('recordBtn');
const recordHint = document.getElementById('recordHint');
const tapToggle = document.getElementById('tapToggle');
const languageSelect = document.getElementById('languageSelect');
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');
const chatMessages = document.getElementById('chatMessages');

// ===== State =====
let ws = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let isTapMode = false;
let audioCtx = null;
let reconnectTimer = null;
let healthTimer = null;

// ===== WebSocket =====
function getWsUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname || 'localhost';
    return `${protocol}//${host}:9000/ws`;
}

function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const url = getWsUrl();
    console.log('Connecting to', url);
    ws = new WebSocket(url);

    ws.onopen = () => {
        console.log('WebSocket connected');
        clearTimeout(reconnectTimer);
        setStatus('ready', 'Ready');
        sendConfig();
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        } catch (err) {
            console.error('Failed to parse message:', err);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        setStatus('error', 'Disconnected');
        scheduleReconnect();
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
    };
}

function scheduleReconnect() {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
        console.log('Attempting reconnect...');
        connectWebSocket();
    }, 3000);
}

function sendConfig() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'config',
            language: languageSelect.value
        }));
    }
}

// ===== Message Handling =====
function handleMessage(msg) {
    switch (msg.type) {
        case 'transcript':
            addChatBubble('user', msg.text);
            break;
        case 'response':
            addChatBubble('bot', msg.text);
            break;
        case 'audio':
            playAudioBase64(msg.data, msg.sample_rate || 24000);
            break;
        case 'status':
            setStatus(msg.status, msg.text || msg.status);
            break;
        case 'error':
            setStatus('error', msg.message || 'Error occurred');
            addChatBubble('bot', 'Error: ' + (msg.message || 'Something went wrong'));
            break;
        default:
            console.log('Unknown message type:', msg.type);
    }
}

// ===== Status =====
function setStatus(state, text) {
    statusIndicator.className = 'status ' + state;
    statusText.textContent = text.charAt(0).toUpperCase() + text.slice(1);
}

// ===== Chat =====
function addChatBubble(role, text) {
    // Remove placeholder if present
    const placeholder = chatMessages.querySelector('.chat-placeholder');
    if (placeholder) placeholder.remove();

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble ' + role;

    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = role === 'user' ? 'You' : 'Bot';

    const content = document.createElement('div');
    content.textContent = text;

    bubble.appendChild(label);
    bubble.appendChild(content);
    chatMessages.appendChild(bubble);

    // Auto-scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ===== Audio Playback (PCM16 24kHz) =====
function getAudioContext() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioCtx;
}

function playAudioBase64(base64Data, sampleRate) {
    try {
        const ctx = getAudioContext();
        const binaryStr = atob(base64Data);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }

        // PCM16 little-endian to Float32
        const pcm16 = new Int16Array(bytes.buffer);
        const numSamples = pcm16.length;
        const audioBuffer = ctx.createBuffer(1, numSamples, sampleRate);
        const channelData = audioBuffer.getChannelData(0);

        for (let i = 0; i < numSamples; i++) {
            channelData[i] = pcm16[i] / 32768.0;
        }

        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        source.onended = () => {
            setStatus('ready', 'Ready');
        };
        source.start();
        setStatus('speaking', 'Speaking');
    } catch (err) {
        console.error('Audio playback error:', err);
    }
}

// ===== Recording =====
async function startRecording() {
    if (isRecording) return;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            const blob = new Blob(audioChunks, { type: 'audio/webm;codecs=opus' });
            sendAudio(blob);
            // Stop all tracks to release mic
            stream.getTracks().forEach(t => t.stop());
        };

        mediaRecorder.start();
        isRecording = true;
        recordBtn.classList.add('recording');
        setStatus('recording', 'Recording');
        recordHint.textContent = isTapMode ? 'Tap to stop' : 'Release to send';
    } catch (err) {
        console.error('Mic access error:', err);
        setStatus('error', 'Microphone access denied');
    }
}

function stopRecording() {
    if (!isRecording || !mediaRecorder) return;

    mediaRecorder.stop();
    isRecording = false;
    recordBtn.classList.remove('recording');
    setStatus('transcribing', 'Transcribing');
    recordHint.textContent = isTapMode ? 'Tap to talk' : 'Hold to talk';
}

function sendAudio(blob) {
    const reader = new FileReader();
    reader.onloadend = () => {
        const base64 = reader.result.split(',')[1];
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'audio',
                data: base64
            }));
        } else {
            setStatus('error', 'Not connected');
        }
    };
    reader.readAsDataURL(blob);
}

// ===== Push-to-talk / Tap-to-talk =====
// Mouse events (desktop)
recordBtn.addEventListener('mousedown', (e) => {
    e.preventDefault();
    if (isTapMode) return;
    startRecording();
});

recordBtn.addEventListener('mouseup', (e) => {
    e.preventDefault();
    if (isTapMode) return;
    stopRecording();
});

recordBtn.addEventListener('mouseleave', (e) => {
    if (isTapMode) return;
    if (isRecording) stopRecording();
});

// Touch events (mobile)
recordBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    if (isTapMode) return;
    startRecording();
});

recordBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    if (isTapMode) return;
    stopRecording();
});

// Tap-to-talk click handler
recordBtn.addEventListener('click', (e) => {
    if (!isTapMode) return;
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

// Toggle mode
tapToggle.addEventListener('change', () => {
    isTapMode = tapToggle.checked;
    recordHint.textContent = isTapMode ? 'Tap to talk' : 'Hold to talk';
    if (isRecording) stopRecording();
});

// Language change
languageSelect.addEventListener('change', () => {
    sendConfig();
});

// ===== Keyboard: Spacebar push-to-talk =====
document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        if (isTapMode) {
            if (!e.repeat) {
                if (isRecording) stopRecording();
                else startRecording();
            }
        } else {
            if (!e.repeat) startRecording();
        }
    }
});

document.addEventListener('keyup', (e) => {
    if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        if (!isTapMode && isRecording) {
            stopRecording();
        }
    }
});

// ===== Health Checks =====
async function checkHealth() {
    const host = window.location.hostname || 'localhost';
    const url = `http://${host}:9000/health/all`;

    try {
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
        const data = await res.json();

        updateHealthDot('health-asr', data.asr);
        updateHealthDot('health-tts', data.tts);
        updateHealthDot('health-llm', data.llm);
        updateHealthDot('health-orchestrator', data.orchestrator);
    } catch (err) {
        // All unknown on fetch failure
        ['health-asr', 'health-tts', 'health-llm', 'health-orchestrator'].forEach(id => {
            updateHealthDot(id, null);
        });
    }
}

function updateHealthDot(elementId, serviceData) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const isHealthy = serviceData && serviceData.status === 'healthy';
    el.className = 'health-item ' + (isHealthy ? 'healthy' : 'unhealthy');
}

// ===== Init =====
function init() {
    connectWebSocket();
    checkHealth();
    healthTimer = setInterval(checkHealth, 30000);
}

init();
