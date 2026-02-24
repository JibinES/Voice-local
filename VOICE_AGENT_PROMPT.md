# Voice Agent - Claude Code Implementation Prompt

> Copy everything below and paste it into Claude Code on your RTX 5090 machine.

---

## Prompt

Build a multilingual voice agent that supports real-time conversation in **6 languages**: Malayalam, Hindi, Tamil, Telugu, Kannada, and English. The entire system runs on a single **NVIDIA RTX 5090 (32GB VRAM)** via Docker containers with GPU sharing. Nothing runs on the host except Docker and the NVIDIA driver.

---

### Hardware & Infrastructure

- **GPU**: NVIDIA RTX 5090, 32GB VRAM, Blackwell architecture (sm_120)
- **CUDA**: 12.8+ required (mandatory for Blackwell/sm_120)
- **Host requirements**: Only NVIDIA driver (570.x+) and Docker with `nvidia-container-toolkit`
- **Base Docker image**: `nvidia/cuda:12.8.0-devel-ubuntu22.04`
- **GPU sharing**: All containers use `--gpus all` and share the single GPU via default CUDA memory allocation. No MPS or MIG needed — the voice pipeline is sequential (ASR → LLM → TTS), so only one model actively computes at a time. Each container reserves its own VRAM portion via `--gpu-memory-utilization` caps.
- **PyTorch**: Must use nightly `2.9.0+cu128` (stable PyTorch has incomplete Blackwell support)
- **vLLM**: Must be built from source with `TORCH_CUDA_ARCH_LIST="12.0"` and `VLLM_FLASH_ATTN_VERSION=2` (Flash Attention 3 does not work on Blackwell yet)

---

### Model Selection (Researched & Validated)

#### ASR — AI4Bharat IndicWhisper (via faster-whisper, INT8)
- **Model**: `ai4bharat/indicwhisper` (fine-tuned Whisper Large on 10,700 hours of Indian language data)
- **Parameters**: 1.55B
- **VRAM**: ~3-6 GB (INT8 quantized via faster-whisper/CTranslate2)
- **Languages**: Hindi (13.8% WER), Kannada (18.3%), Tamil (25.3%), Telugu (28.8%), Malayalam (32.3%), English (~3-5%)
- **Why this model**: Lowest published WER on Indian languages across 39/59 Vistaar benchmarks. Beats Google STT on 57/59 benchmarks. 4.1% average WER improvement over vanilla Whisper.
- **Serving**: **faster-whisper-server** (`fedirz/faster-whisper-server`, 3.5k+ GitHub stars). Production-grade ASR server with OpenAI-compatible API, streaming WebSocket transcription, Silero VAD integration, and official Docker images. Convert IndicWhisper HuggingFace checkpoint to CTranslate2 format, then point faster-whisper-server at it.
- **Fallback**: For English-primary traffic, also load `openai/whisper-large-v3-turbo` via faster-whisper-server (~2.5GB VRAM, 809M params) as a secondary model
- **Docker port**: 8001
- **API**: OpenAI-compatible `/v1/audio/transcriptions` endpoint (drop-in replacement for OpenAI's Whisper API)

#### TTS — svara-TTS v1 (All languages in one model)
- **Model**: `kenpath/svara-tts-v1` (248K+ downloads/month)
- **Architecture**: Llama-3.2-3B fine-tuned for discrete audio token prediction (Orpheus-style) + SNAC codec decoder
- **Parameters**: 3B
- **VRAM**: ~7 GB (BF16 via vLLM, the only verified option). Can try `--quantization fp8` to drop to ~3.5GB after load (but needs ~7GB during initial model load). GGUF Q4_K_M (2.1GB) available for llama.cpp but SNAC decoder still needs ~1GB GPU separately.
- **Languages**: All 6 needed + 13 more (19 total): Hindi, Malayalam, Tamil, Telugu, Kannada, English (Indian accent), Bengali, Marathi, Gujarati, Punjabi, Assamese, etc.
- **Voices**: 38 voice profiles (male + female per language). **Default: use `hi_female` for Hindi, `ml_female` for Malayalam, `ta_female` for Tamil, `te_female` for Telugu, `kn_female` for Kannada, `en_female` for English**
- **Emotion tags**: `<happy>`, `<sad>`, `<anger>`, `<fear>`, `<surprise>`, `<chat>`, `<clear>` — append at end of text
- **Streaming**: YES — chunked HTTP streaming via vLLM SSE → 28-token SNAC sliding window → PCM16 audio chunks
- **Output**: 24kHz, 16-bit PCM mono. Supports wav, mp3, opus, aac via ffmpeg conversion.
- **Latency**: ~200-500ms time-to-first-audio-chunk (streaming), real-time factor < 1.0
- **License**: Apache 2.0
- **Why this model**: Only model that covers all 5 Indian languages + English with streaming, emotion control, voice cloning, and a production-ready Docker setup. 248K downloads/month — most popular Indian TTS model.
- **Serving**: Self-contained Docker setup from `github.com/Kenpath/svara-tts-inference`. Internally runs vLLM (for token generation) + FastAPI (for HTTP API + SNAC audio decoding). Uses supervisord to manage both processes.
- **Docker port**: 8002 (FastAPI API), internal vLLM on port 8003 (not exposed to host)
- **API endpoint**: `POST /v1/text-to-speech`
  ```json
  {
    "text": "നമസ്കാരം, സുഖമാണോ?",
    "voice_id": "ml_female",
    "stream": true,
    "output_format": "pcm"
  }
  ```
- **Voice ID format**: `{lang_code}_{gender}` — e.g., `hi_female`, `ta_male`, `ml_female`, `te_female`, `kn_female`, `en_female`
- **Important**: svara-TTS runs its OWN internal vLLM instance (separate from the LLM service). Cap its GPU memory with `VLLM_GPU_MEMORY_UTILIZATION=0.2` (~6.4GB) in its `.env` to leave room for the LLM and ASR services.

#### LLM — OpenAI GPT-OSS-20B (MXFP4)
- **Model**: `openai/gpt-oss-20b`
- **Parameters**: 21B total, 3.6B active (Mixture-of-Experts architecture)
- **VRAM**: ~12-16 GB (MXFP4 quantized natively)
- **Serving**: vLLM (built from source for Blackwell)
- **License**: Apache 2.0
- **Note**: English-biased training. For Indian language understanding, the ASR transcription should be in the target language script, and the LLM response can be in English or transliterated. If deeper Indian language generation is needed, consider fine-tuning or supplementing with AI4Bharat Indic LLMs.
- **Docker port**: 8000
- **API**: OpenAI-compatible `/v1/chat/completions`

---

### VRAM Budget (Must Fit in 32GB)

```
Component                          VRAM       Flag
──────────────────────────────────────────────────────────────
LLM  (GPT-OSS-20B vLLM)           15 GB  ←  --gpu-memory-utilization 0.46875 (15/32)
TTS  (svara-TTS v1 internal vLLM)  ~6 GB  ←  VLLM_GPU_MEMORY_UTILIZATION=0.2
     (+ SNAC decoder)              ~1 GB
ASR  (IndicWhisper INT8)           ~4 GB
CUDA overhead                      ~2 GB
──────────────────────────────────────────────────────────────
TOTAL                             ~28 GB
Headroom                           ~4 GB
```

> Two separate vLLM instances run: one for LLM (port 8000), one inside svara-TTS for audio token generation (port 8003 internal). Each is capped via `--gpu-memory-utilization`. The LLM gets 15GB (weights ~12GB MXFP4 + ~3GB KV-cache for single-user), TTS gets ~7GB (3B model BF16 + SNAC). 4GB headroom for burst traffic.

---

### Architecture

```
┌──────────────────────────────────────────────────────┐
│                   RTX 5090 (32GB)                    │
│               Shared via --gpus all                  │
│                                                      │
│  ┌────────────────┐ ┌──────────────────┐ ┌───────────────┐│
│  │  ASR Service    │ │  TTS Service     │ │  LLM Service  ││
│  │  Port: 8001     │ │  Port: 8002      │ │  Port: 8000   ││
│  │                 │ │                  │ │               ││
│  │ faster-whisper- │ │ svara-TTS v1     │ │ vLLM          ││
│  │ server          │ │ (internal vLLM   │ │               ││
│  │ (IndicWhisper   │ │  + SNAC decoder  │ │ GPT-OSS-20B   ││
│  │  CT2, INT8)     │ │  + FastAPI)      │ │ (MXFP4)       ││
│  │ ~4GB VRAM       │ │ ~7GB VRAM        │ │ ~15GB VRAM    ││
│  └───────┬─────────┘ └────────┬─────────┘ └───────┬───────┘│
│          │                    │                    │        │
└──────────┼────────────────────┼────────────────────┼────────┘
           │                   │                   │
    ┌──────┴───────────────────┴───────────────────┴──────┐
    │              Pipecat Voice Pipeline (No GPU)         │
    │              Port: 9000                              │
    │                                                      │
    │  Silero VAD → ASR → LLM → TTS → Audio Out           │
    │  Interruption handling, turn-taking, streaming       │
    │  Connects to all 3 services via OpenAI-compatible API│
    └──────────────────────┬───────────────────────────────┘
                           │
    ┌──────────────────────┴───────────────────────────────┐
    │              Test UI (No GPU)                         │
    │              Port: 3000                               │
    │                                                      │
    │  Browser-based push-to-talk interface                 │
    │  Mic recording → WebSocket → Audio playback           │
    │  Language selector, chat history, health dashboard     │
    └──────────────────────────────────────────────────────┘
```

---

### Project Structure

```
voice-bot/
├── docker-compose.yml              # All services defined here
├── setup.sh                        # One-click deployment script
├── .env                            # GPU device, ports, model paths
│
├── services/
│   ├── asr/
│   │   ├── Dockerfile              # Based on faster-whisper-server image
│   │   ├── model_converter.py      # HF IndicWhisper → CTranslate2 conversion
│   │   └── config.yaml             # faster-whisper-server configuration
│   │
│   ├── tts/
│   │   ├── Dockerfile              # Based on svara-tts-inference (CUDA 12.8 + vLLM + SNAC)
│   │   ├── .env                    # VLLM_GPU_MEMORY_UTILIZATION=0.2, voice defaults
│   │   └── supervisord.conf        # Manages internal vLLM (port 8003) + FastAPI (port 8002)
│   │
│   ├── llm/
│   │   ├── Dockerfile              # vLLM built from source for Blackwell
│   │   ├── start_vllm.sh           # vLLM launch with --gpu-memory-utilization 0.625
│   │   └── config.py
│   │
│   └── orchestrator/
│       ├── Dockerfile              # Lightweight, no GPU needed
│       ├── requirements.txt        # pipecat-ai, silero-vad, websockets
│       ├── bot.py                  # Pipecat pipeline: VAD → ASR → LLM → TTS
│       ├── svara_tts_service.py    # Custom Pipecat TTS adapter for svara-TTS API
│       ├── transport.py            # WebSocket transport for browser UI
│       ├── language_router.py      # Maps detected language → voice_id (e.g., "ml" → "ml_female")
│       └── config.py
│
├── ui/
│   ├── Dockerfile                  # Lightweight nginx or static file server
│   ├── index.html                  # Single-page test UI (all-in-one)
│   ├── style.css
│   └── app.js                      # WebSocket client + mic recording logic
│
├── scripts/
│   ├── setup_host.sh               # Install nvidia-container-toolkit on host
│   ├── download_models.sh          # Pre-download all model weights
│   └── test_pipeline.sh            # End-to-end test with sample audio
│
└── tests/
    ├── test_asr.py
    ├── test_tts.py
    ├── test_llm.py
    └── sample_audio/               # Test audio files in each language
```

---

### setup.sh — One-Click Deployment Script

The `setup.sh` script should do the following in order:

1. **Pre-flight checks**: Verify NVIDIA driver version (>=570.x), Docker installed, `nvidia-container-toolkit` installed, GPU detected as RTX 5090
2. **Create model cache volume**: `docker volume create voice-bot-models` (persistent model storage)
4. **Download ALL models upfront** (before any container starts). Use `huggingface-cli` inside a temporary download container. All models are saved to the shared `voice-bot-models` Docker volume so containers don't re-download on restart:
   ```bash
   # Run a temporary container to download all models into the shared volume
   docker run --rm -v voice-bot-models:/models \
     -e HF_HUB_ENABLE_HF_TRANSFER=1 \
     python:3.11-slim bash -c '
       pip install huggingface_hub[hf_transfer] ctranslate2 transformers torch --quiet &&

       echo "=== [1/3] Downloading GPT-OSS-20B (~13GB) ===" &&
       huggingface-cli download openai/gpt-oss-20b --local-dir /models/gpt-oss-20b &&

       echo "=== [2/3] Downloading svara-TTS v1 (~13GB) ===" &&
       huggingface-cli download kenpath/svara-tts-v1 --local-dir /models/svara-tts-v1 &&

       echo "=== [3/3] Downloading IndicWhisper + converting to CTranslate2 ===" &&
       huggingface-cli download ai4bharat/indicwhisper --local-dir /models/indicwhisper-hf &&
       ct2-opus-mt-converter --model /models/indicwhisper-hf --output_dir /models/indicwhisper-ct2 --quantization int8 &&

       echo "=== All models downloaded ==="
     '
   ```
   Total download: ~30-35GB. The script should show progress bars and verify checksums.
   If any download fails, the script should retry up to 3 times before exiting with an error.
5. **Build Docker images**: `docker compose build`
6. **Start all services**: `docker compose up -d`
7. **Health checks**: Wait for all services to report healthy, then run a quick test transcription + generation + synthesis
8. **Print status**: Show service URLs and VRAM usage

---

### Docker Compose Configuration

Each service must have:
- `deploy.resources.reservations.devices` with `driver: nvidia, count: 1, capabilities: [gpu]`
- Shared model volume mounted at `/models`
- Health check endpoint
- Restart policy: `unless-stopped`

The orchestrator container does NOT need GPU access — it only coordinates HTTP calls between services.

---

### Serving Frameworks

| Component | Server | GitHub | API |
|-----------|--------|--------|-----|
| **ASR** | `faster-whisper-server` | `fedirz/faster-whisper-server` (3.5k stars) | OpenAI `/v1/audio/transcriptions` |
| **TTS** | `svara-TTS v1` | `Kenpath/svara-tts-inference` (248K dl/mo) | `/v1/text-to-speech` (streaming) |
| **LLM** | `vLLM` | `vllm-project/vllm` (45k stars) | OpenAI `/v1/chat/completions` |
| **Pipeline** | `Pipecat` | `pipecat-ai/pipecat` (5k stars) | WebSocket transport |

All three model servers expose **OpenAI-compatible APIs**, so Pipecat connects to them using its built-in OpenAI service classes — no custom adapters needed.

---

### Key Implementation Details

#### ASR Service (Port 8001) — faster-whisper-server
```bash
# Use the official faster-whisper-server Docker image
# Point it at the IndicWhisper model converted to CTranslate2 format
docker run --gpus all -p 8001:8000 \
    -v /models:/models \
    -e WHISPER__MODEL=/models/indicwhisper-ct2 \
    -e WHISPER__COMPUTE_TYPE=int8 \
    -e WHISPER__DEVICE=cuda \
    fedirz/faster-whisper-server:latest

# Provides:
# POST /v1/audio/transcriptions  (OpenAI-compatible, file upload)
# WS   /v1/audio/transcriptions  (streaming WebSocket for real-time)
# Includes Silero VAD for automatic speech segmentation
```

#### TTS Service (Port 8002) — svara-TTS v1
```bash
# svara-TTS has its own complete Docker setup from github.com/Kenpath/svara-tts-inference
# It runs TWO processes internally via supervisord:
#   1. vLLM (port 8003 internal) — generates audio tokens from text
#   2. FastAPI (port 8002 exposed) — HTTP API + SNAC audio decoder

# Key .env settings for the TTS container:
VLLM_MODEL=kenpath/svara-tts-v1
VLLM_PORT=8003                          # Internal, not exposed to host
VLLM_GPU_MEMORY_UTILIZATION=0.2         # Cap at ~6.4GB VRAM (critical for sharing GPU)
VLLM_MAX_MODEL_LEN=2048
API_HOST=0.0.0.0
API_PORT=8002
VLLM_BASE_URL=http://localhost:8003/v1  # FastAPI connects to internal vLLM
TTS_DEVICE=cuda                         # SNAC decoder runs on GPU

# API Usage:
# POST /v1/text-to-speech (streaming)
curl -X POST http://localhost:8002/v1/text-to-speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "നമസ്കാരം, എനിക്ക് സഹായിക്കാൻ കഴിയുമോ?",
    "voice_id": "ml_female",
    "stream": true,
    "output_format": "wav"
  }' --output response.wav

# Voice IDs for your 6 languages (default to female):
#   Hindi:     hi_female    |  Malayalam:  ml_female
#   Tamil:     ta_female    |  Telugu:     te_female
#   Kannada:   kn_female    |  English:    en_female
#
# Emotion: append at end of text — e.g., "text here <happy>"
# Tags: <happy>, <sad>, <anger>, <fear>, <surprise>, <chat>, <clear>

# Other endpoints:
# GET  /v1/voices          — list all 38 available voices
# GET  /health             — health check
```

#### LLM Service (Port 8000) — vLLM
```bash
# vLLM launch command (built from source for Blackwell)
# --gpu-memory-utilization 0.46875 caps vLLM to 15GB of the 32GB RTX 5090 (15/32 = 0.46875)
# LLM weights are ~12GB (MXFP4), leaving ~3GB for KV-cache (enough for single-user)
# Remaining ~17GB shared by ASR (~4GB) + TTS (~7GB) + CUDA overhead (~2GB) + headroom (~4GB)
python -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-20b \
    --served-model-name gpt-oss-20b \
    --dtype auto \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.46875 \
    --port 8000 \
    --trust-remote-code \
    --enforce-eager
# --enforce-eager disables CUDA graph capture, saving ~1-2GB VRAM overhead
# Remove it if you want slightly faster inference and can spare the memory

# Provides:
# POST /v1/chat/completions  (OpenAI-compatible, streaming SSE)
```

#### Orchestrator / Voice Pipeline (Port 9000) — Pipecat
```python
# Pipecat pipeline — handles the full voice conversation loop
# No GPU needed, runs on CPU in its own container

from pipecat.pipeline.pipeline import Pipeline
from pipecat.services.openai import OpenAILLMService
from pipecat.services.whisper import WhisperSTTService
from pipecat.vad.silero import SileroVADAnalyzer
from pipecat.transports.websocket import WebSocketTransport

# ASR + LLM use OpenAI-compatible APIs (Pipecat built-in adapters)
stt = WhisperSTTService(base_url="http://asr:8001/v1")
llm = OpenAILLMService(base_url="http://llm:8000/v1", model="gpt-oss-20b")

# TTS: svara-TTS uses a custom endpoint (/v1/text-to-speech, not OpenAI's /v1/audio/speech)
# Write a custom Pipecat TTS service that:
#   1. POSTs to http://tts:8002/v1/text-to-speech with {text, voice_id, stream: true}
#   2. Receives streaming PCM16 chunks (24kHz mono)
#   3. Routes voice_id by detected language: hi_female, ml_female, ta_female, te_female, kn_female, en_female
tts = SvaraTTSService(base_url="http://tts:8002", default_voice="hi_female")

# Pipecat handles automatically:
# - Silero VAD — detects when user starts/stops speaking
# - Interruption handling — stops TTS playback if user speaks mid-response
# - Turn-taking — manages who is "speaking" (user vs agent)
# - Streaming — LLM tokens stream directly to TTS for low latency
# - Audio buffering — smooth playback without gaps

pipeline = Pipeline([
    transport.input(),    # Audio from browser WebSocket
    vad,                  # Silero VAD: detect speech boundaries
    stt,                  # ASR: audio → text (+ language detection)
    llm,                  # LLM: text → response (streaming)
    tts,                  # TTS: response → audio (streaming PCM16 24kHz)
    transport.output(),   # Audio back to browser WebSocket
])

# Also expose REST endpoint for simple request/response:
# POST /v1/voice/chat
# Body: multipart with audio file + optional language hint
# Return: audio/wav response
```

---

### Test UI (Port 3000)

Build a simple browser-based test UI served at `http://localhost:3000`. It should be a **single-page HTML/CSS/JS app** (no build tools, no React — just vanilla HTML) served by a lightweight container (nginx or Python `http.server`). No GPU needed.

**Features:**
1. **Language selector** — dropdown to pick: Malayalam, Hindi, Tamil, Telugu, Kannada, English (or "Auto-detect")
2. **Push-to-talk button** — hold to record from browser microphone (uses `MediaRecorder` API)
3. **Tap-to-talk toggle** — alternative: tap once to start, tap again to stop
4. **Live transcript panel** — shows the ASR transcription as it comes back
5. **LLM response panel** — shows the text response from GPT-OSS-20B
6. **Audio playback** — auto-plays the TTS audio response in the browser
7. **Conversation history** — scrollable chat-style view showing the full back-and-forth
8. **Status indicators** — show which stage is active (Recording → Transcribing → Thinking → Speaking)
9. **Service health dashboard** — small panel showing green/red status for ASR, TTS, LLM, Orchestrator

**Implementation:**
```javascript
// Connect to orchestrator via WebSocket
const ws = new WebSocket("ws://localhost:9000/ws");

// Record audio from mic using MediaRecorder API
// Send audio blob to WebSocket when user releases push-to-talk
// Receive JSON messages back: {type: "transcript", text: "..."}, {type: "response", text: "..."}, {type: "audio", data: base64}
// Play audio using AudioContext or <audio> element
```

**Also support the REST fallback:**
```
POST http://localhost:9000/v1/voice/chat
Content-Type: multipart/form-data
Body: audio file + language hint
Response: audio/wav
```

This UI runs in its own Docker container (no GPU) and is included in `docker-compose.yml`. It should look clean and functional — dark theme, large buttons, mobile-friendly layout so it works on a phone browser too.

---

### Critical RTX 5090 / Blackwell Gotchas

1. **vLLM must be built from source** — no precompiled wheels for sm_120 yet
2. **Set `VLLM_FLASH_ATTN_VERSION=2`** — Flash Attention 3 crashes on Blackwell
3. **Use PyTorch nightly `cu128`** — stable releases don't fully support Blackwell
4. **Set `TORCH_CUDA_ARCH_LIST="12.0"`** when building vLLM
5. **Do NOT use TensorFlow** — known CUDA initialization failures on RTX 5090
6. **Use `ubuntu22.04`** base images — 24.04 has driver compatibility issues

---

### Deliverables

1. All Dockerfiles that build successfully with CUDA 12.8 on Blackwell
2. `docker-compose.yml` that brings up all 5 services (ASR, TTS, LLM, Orchestrator, UI)
3. `setup.sh` that handles everything from model download to service startup
4. Working WebSocket endpoint at `ws://localhost:9000/ws` for real-time voice chat
5. REST endpoint at `http://localhost:9000/v1/voice/chat` for single-turn voice interaction
6. **Test UI at `http://localhost:3000`** — browser-based push-to-talk interface with mic recording, live transcription, LLM response display, TTS audio playback, conversation history, and service health dashboard
7. Health check script that verifies all services and prints VRAM usage
8. All services must start, serve requests, and stay healthy without any host dependencies beyond Docker + NVIDIA driver
