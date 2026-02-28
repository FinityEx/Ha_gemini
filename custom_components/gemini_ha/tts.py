"""Text-to-speech platform for Gemini HA.

Uses the Gemini Live API to generate natural-sounding audio responses.
"""
from __future__ import annotations

import io
import logging
import struct

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_API_KEY,
    CONF_TTS_VOICE,
    DEFAULT_TTS_VOICE,
    DOMAIN,
    SUPPORTED_TTS_VOICES,
)

_LOGGER = logging.getLogger(__name__)

# Live API audio output: 16-bit signed PCM, mono, 24 kHz.
_PCM_SAMPLE_RATE = 24_000
_PCM_CHANNELS = 1
_PCM_BITS = 16

# Live API model that supports audio output modality.
_TTS_MODEL = "gemini-2.0-flash-live-001"

# Maximum number of response chunks before giving up.
_MAX_CHUNKS = 512


def _pcm_to_wav(pcm_data: bytes) -> bytes:
    """Wrap raw 16-bit LE PCM bytes in a WAVE container."""
    buf = io.BytesIO()
    data_size = len(pcm_data)
    byte_rate = _PCM_SAMPLE_RATE * _PCM_CHANNELS * _PCM_BITS // 8
    block_align = _PCM_CHANNELS * _PCM_BITS // 8

    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))  # PCM format
    buf.write(struct.pack("<H", _PCM_CHANNELS))
    buf.write(struct.pack("<I", _PCM_SAMPLE_RATE))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", _PCM_BITS))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm_data)
    return buf.getvalue()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Gemini TTS entity."""
    _LOGGER.debug("Setting up Gemini TTS entity for entry %s", config_entry.entry_id)
    async_add_entities([GeminiTTSEntity(config_entry)])


class GeminiTTSEntity(TextToSpeechEntity):
    """Gemini Live API text-to-speech entity.

    Connects to the Gemini Live API with AUDIO response modality,
    sends the text turn, collects the audio chunks, and returns a
    WAV-wrapped PCM byte string.
    """

    _attr_name = "Gemini TTS"
    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise the TTS entity."""
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_tts"

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["en"]

    @property
    def default_options(self) -> dict:
        """Return default TTS options."""
        return {
            "voice": self._config_entry.options.get(CONF_TTS_VOICE, DEFAULT_TTS_VOICE)
        }

    @property
    def supported_options(self) -> list[str]:
        """Return supported TTS options."""
        return ["voice"]

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict | None = None,
    ) -> TtsAudioType:
        """Generate TTS audio via the Gemini Live API."""
        import base64  # noqa: PLC0415

        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        voice: str = (options or {}).get(
            "voice",
            self._config_entry.options.get(CONF_TTS_VOICE, DEFAULT_TTS_VOICE),
        )
        if voice not in SUPPORTED_TTS_VOICES:
            _LOGGER.warning(
                "TTS voice '%s' is not supported; falling back to '%s'",
                voice,
                DEFAULT_TTS_VOICE,
            )
            voice = DEFAULT_TTS_VOICE

        _LOGGER.debug(
            "TTS generation started: voice=%s, language=%s, message_length=%d chars",
            voice,
            language,
            len(message),
        )

        api_key: str = self._config_entry.data[CONF_API_KEY]
        client = genai.Client(api_key=api_key)

        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice,
                    )
                )
            ),
        )

        try:
            audio_chunks: list[bytes] = []

            async with client.aio.live.connect(
                model=_TTS_MODEL, config=live_config
            ) as session:
                await session.send(input=message, end_of_turn=True)

                chunk_count = 0
                async for msg in session.receive():
                    server_content = msg.server_content
                    if server_content is not None:
                        model_turn = server_content.model_turn
                        if model_turn is not None:
                            for part in model_turn.parts or []:
                                if part.inline_data and part.inline_data.data:
                                    decoded = base64.b64decode(part.inline_data.data)
                                    audio_chunks.append(decoded)
                                    _LOGGER.debug(
                                        "TTS received audio chunk (total so far: %d, chunk size: %d bytes)",
                                        len(audio_chunks),
                                        len(decoded),
                                    )
                        if server_content.turn_complete:
                            _LOGGER.debug("TTS turn complete signal received")
                            break

                    chunk_count += 1
                    if chunk_count >= _MAX_CHUNKS:
                        _LOGGER.warning(
                            "Gemini TTS: reached max chunks (%d), stopping early",
                            _MAX_CHUNKS,
                        )
                        break

            if not audio_chunks:
                _LOGGER.error("Gemini TTS returned no audio data")
                return None

            pcm_data = b"".join(audio_chunks)
            _LOGGER.debug(
                "TTS generation complete: %d chunks, %d total PCM bytes",
                len(audio_chunks),
                len(pcm_data),
            )
            wav_bytes = _pcm_to_wav(pcm_data)
            return ("wav", wav_bytes)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Gemini TTS generation failed: %s", err)
            return None
