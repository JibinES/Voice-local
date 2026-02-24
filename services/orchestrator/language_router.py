LANGUAGE_VOICE_MAP = {
    "hi": "hi_female",
    "ml": "ml_female",
    "ta": "ta_female",
    "te": "te_female",
    "kn": "kn_female",
    "en": "en_female",
}

def get_voice_id(language_code: str, gender: str = "female") -> str:
    """Get voice ID from language code. Falls back to Hindi."""
    # Normalize language code (e.g., "hi-IN" -> "hi")
    lang = language_code.split("-")[0].lower() if language_code else "hi"
    voice = f"{lang}_{gender}"
    if lang in LANGUAGE_VOICE_MAP:
        return LANGUAGE_VOICE_MAP[lang] if gender == "female" else f"{lang}_{gender}"
    return "hi_female"  # fallback

def get_language_name(code: str) -> str:
    names = {"hi": "Hindi", "ml": "Malayalam", "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "en": "English"}
    lang = code.split("-")[0].lower() if code else "hi"
    return names.get(lang, "Hindi")
