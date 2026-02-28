"""Speech-to-text platform for Gemini HA.

Uses the Gemini audio-understanding API to transcribe audio streams.
"""
from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterable

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_API_KEY, CONF_STT_LANGUAGE, DEFAULT_STT_LANGUAGE, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Mapping from HA AudioFormats to MIME types accepted by the Gemini API.
_FORMAT_TO_MIME: dict[AudioFormats, str] = {
    AudioFormats.WAV: "audio/wav",
    AudioFormats.OGG: "audio/ogg",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Gemini STT entity."""
    _LOGGER.debug("Setting up Gemini STT entity for entry %s", config_entry.entry_id)
    async_add_entities([GeminiSTTEntity(config_entry)])


class GeminiSTTEntity(SpeechToTextEntity):
    """Gemini Live API speech-to-text entity.

    Buffers the incoming audio stream and sends it to the Gemini API
    for transcription using audio-understanding capabilities.
    """

    _attr_name = "Gemini STT"
    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise the STT entity."""
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_stt"

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return [
            self._config_entry.options.get(CONF_STT_LANGUAGE, DEFAULT_STT_LANGUAGE)
        ]

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return supported audio formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return supported audio codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self,
        metadata: SpeechMetadata,
        stream: AsyncIterable[bytes],
    ) -> SpeechResult:
        """Transcribe an audio stream using the Gemini API."""
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        language = self._config_entry.options.get(CONF_STT_LANGUAGE, DEFAULT_STT_LANGUAGE)
        _LOGGER.debug(
            "STT processing started: format=%s, codec=%s, sample_rate=%s, language=%s",
            metadata.format,
            metadata.codec,
            metadata.sample_rate,
            language,
        )

        # Buffer the entire stream.
        audio_data = bytearray()
        async for chunk in stream:
            audio_data += chunk

        _LOGGER.debug("STT audio buffer collected: %d bytes", len(audio_data))

        if not audio_data:
            _LOGGER.warning("STT received empty audio stream")
            return SpeechResult("", SpeechResultState.ERROR)

        api_key: str = self._config_entry.data[CONF_API_KEY]
        mime_type = _FORMAT_TO_MIME.get(metadata.format, "audio/wav")
        _LOGGER.debug("STT sending to Gemini API (mime_type=%s)", mime_type)

        try:
            client = genai.Client(api_key=api_key)

            audio_part = types.Part(
                inline_data=types.Blob(
                    mime_type=mime_type,
                    data=base64.b64encode(bytes(audio_data)).decode(),
                )
            )
            instruction_part = types.Part(
                text="Transcribe this audio exactly as spoken. Return only the transcript text, nothing else."
            )

            response = await self.hass.async_add_executor_job(
                lambda: client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[types.Content(parts=[audio_part, instruction_part])],
                )
            )

            text: str = (response.text or "").strip()
            if text:
                _LOGGER.debug("STT transcription succeeded: %d characters", len(text))
                return SpeechResult(text, SpeechResultState.SUCCESS)
            _LOGGER.warning("STT transcription returned empty text")
            return SpeechResult("", SpeechResultState.ERROR)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Gemini STT transcription failed: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)
