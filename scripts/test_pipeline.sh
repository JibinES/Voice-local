#!/bin/bash
set -euo pipefail

# =============================================================================
# End-to-end pipeline test
# =============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
error(){ echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

BASE_URL="${1:-http://localhost}"
PASSED=0
FAILED=0

test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_code="${3:-200}"

    info "Testing $name..."
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [ "$status" = "$expected_code" ]; then
        log "$name — HTTP $status"
        PASSED=$((PASSED + 1))
    else
        error "$name — HTTP $status (expected $expected_code)"
        FAILED=$((FAILED + 1))
    fi
}

echo "============================================================"
echo "  Voice Bot — End-to-End Pipeline Test"
echo "============================================================"
echo ""

# Health checks
test_endpoint "LLM Health"          "$BASE_URL:8000/health"
test_endpoint "ASR Health"          "$BASE_URL:8001/health"
test_endpoint "TTS Health"          "$BASE_URL:8002/health"
test_endpoint "Orchestrator Health" "$BASE_URL:9000/health"
test_endpoint "UI"                  "$BASE_URL:3000/"
test_endpoint "All Services Health" "$BASE_URL:9000/health/all"

echo ""

# Test LLM
info "Testing LLM chat completion..."
LLM_RESPONSE=$(curl -s -X POST "$BASE_URL:8000/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "gpt-oss-20b",
        "messages": [{"role": "user", "content": "Say hello in Hindi"}],
        "max_tokens": 50
    }' 2>/dev/null)

if echo "$LLM_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'])" 2>/dev/null; then
    log "LLM response received"
    PASSED=$((PASSED + 1))
else
    error "LLM test failed: $LLM_RESPONSE"
    FAILED=$((FAILED + 1))
fi

# Test TTS
info "Testing TTS synthesis..."
TTS_STATUS=$(curl -s -o /tmp/voice-bot-test.wav -w "%{http_code}" \
    -X POST "$BASE_URL:8002/v1/text-to-speech" \
    -H "Content-Type: application/json" \
    -d '{"text": "Hello, this is a test.", "voice_id": "en_female", "stream": false, "output_format": "wav"}' \
    2>/dev/null)

if [ "$TTS_STATUS" = "200" ] && [ -s /tmp/voice-bot-test.wav ]; then
    log "TTS audio generated ($(wc -c < /tmp/voice-bot-test.wav) bytes)"
    PASSED=$((PASSED + 1))
else
    error "TTS test failed: HTTP $TTS_STATUS"
    FAILED=$((FAILED + 1))
fi

# Test ASR (using TTS output if available)
if [ -s /tmp/voice-bot-test.wav ]; then
    info "Testing ASR transcription..."
    ASR_RESPONSE=$(curl -s -X POST "$BASE_URL:8001/v1/audio/transcriptions" \
        -F "file=@/tmp/voice-bot-test.wav" \
        -F "model=indicwhisper" 2>/dev/null)

    if echo "$ASR_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('text',''))" 2>/dev/null; then
        log "ASR transcription received"
        PASSED=$((PASSED + 1))
    else
        error "ASR test failed: $ASR_RESPONSE"
        FAILED=$((FAILED + 1))
    fi
fi

# Cleanup
rm -f /tmp/voice-bot-test.wav

echo ""
echo "============================================================"
echo "  Results: $PASSED passed, $FAILED failed"
echo "============================================================"

[ $FAILED -eq 0 ] && exit 0 || exit 1
