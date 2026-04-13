import logging
from typing import Literal

from openai import OpenAI

from Chatbot.backend.app.core.settings import settings

from .base import TTSProvider, TTSResult
from .errors import TTSProviderFailureError, TTSProviderUnavailableError

logger = logging.getLogger("queueiq.rag.tts.openai")

_AUDIO_CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
}

_AUDIO_FORMAT_ALIASES = {
    "mpeg": "mp3",
    "wave": "wav",
}

_LANGUAGE_HINTS: dict[str, str] = {
    "en": "Speak naturally in English.",
    "fr": "Speak naturally in French.",
    "es": "Speak naturally in Spanish.",
}


class OpenAITTSProvider(TTSProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise TTSProviderUnavailableError("OPENAI_API_KEY is not configured")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = str(settings.openai_tts_model or "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts"
        self._voice = str(settings.openai_tts_voice or "coral").strip() or "coral"
        self._instructions = str(settings.openai_tts_instructions or "").strip()
        configured_format = str(settings.openai_tts_audio_format or "mp3").strip().lower() or "mp3"
        configured_format = _AUDIO_FORMAT_ALIASES.get(configured_format, configured_format)
        if configured_format not in _AUDIO_CONTENT_TYPES:
            logger.warning(
                "Unsupported OPENAI_TTS_AUDIO_FORMAT '%s'; falling back to 'mp3'",
                configured_format,
            )
            configured_format = "mp3"
        self._audio_format = configured_format
        self._content_type = _AUDIO_CONTENT_TYPES.get(self._audio_format, "audio/mpeg")
        self._speed = max(0.25, min(float(settings.openai_tts_speed), 4.0))

    def synthesize(self, *, text: str, language: Literal["en", "fr", "es"] | None = None) -> TTSResult:
        if not text:
            raise TTSProviderFailureError("Text payload is empty")
        try:
            language_hint = _LANGUAGE_HINTS.get(str(language or "").strip().lower())
            instructions_parts = [self._instructions] if self._instructions else []
            if language_hint:
                instructions_parts.append(language_hint)
            merged_instructions = " ".join(part for part in instructions_parts if part).strip()
            request_payload = {
                "model": self._model,
                "voice": self._voice,
                "input": text,
                "response_format": self._audio_format,
                "speed": self._speed,
            }
            if merged_instructions:
                request_payload["instructions"] = merged_instructions
            response = self._client.audio.speech.create(**request_payload)
            audio_bytes = bytes(getattr(response, "content", b"") or b"")
            if not audio_bytes and hasattr(response, "read"):
                audio_bytes = bytes(response.read() or b"")
            if not audio_bytes:
                raise TTSProviderFailureError("OpenAI TTS returned empty audio")
            return TTSResult(
                audio_bytes=audio_bytes,
                provider=self.provider_name,
                audio_format=self._audio_format,
                content_type=self._content_type,
            )
        except TTSProviderFailureError:
            raise
        except Exception as exc:
            logger.exception("OpenAI text-to-speech failed")
            raise TTSProviderFailureError("Text-to-speech request failed") from exc
