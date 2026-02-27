"""Constants for the Gemini HA integration."""

DOMAIN = "gemini_ha"

CONF_API_KEY = "api_key"
CONF_CHAT_MODEL = "chat_model"
CONF_STT_LANGUAGE = "stt_language"
CONF_TTS_VOICE = "tts_voice"

DEFAULT_CHAT_MODEL = "gemini-2.0-flash-live-001"
DEFAULT_STT_LANGUAGE = "en-US"
DEFAULT_TTS_VOICE = "Zephyr"

SUPPORTED_STT_LANGUAGES = [
    "en-US",
    "de-DE",
    "es-ES",
    "fr-FR",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "pt-BR",
    "zh-CN",
]

SUPPORTED_TTS_VOICES = [
    "Aoede",
    "Charon",
    "Fenrir",
    "Kore",
    "Leda",
    "Orus",
    "Puck",
    "Zephyr",
]

PLATFORMS = ["stt", "tts", "conversation"]
