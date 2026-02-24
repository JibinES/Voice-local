import os

ASR_BASE_URL = os.getenv("ASR_BASE_URL", "http://asr:8001")
TTS_BASE_URL = os.getenv("TTS_BASE_URL", "http://tts:8002")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://llm:8000")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-oss-20b")
ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "9000"))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "hi")
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "hi_female")
SYSTEM_PROMPT = """You are a helpful multilingual voice assistant. You can converse in Hindi, Malayalam, Tamil, Telugu, Kannada, and English. Keep responses concise and natural for spoken conversation. Respond in the same language the user speaks in."""
