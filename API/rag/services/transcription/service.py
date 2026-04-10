from pathlib import Path

from Chatbot.backend.app.core.settings import settings

from .base import TranscriptionResult
from .errors import (
    TranscriptionFeatureDisabledError,
    TranscriptionProviderUnavailableError,
    TranscriptionValidationError,
)
from .openai_provider import OpenAITranscriptionProvider

SUPPORTED_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
}
SUPPORTED_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}
MAX_BYTES_PER_SECOND = 64_000


class TranscriptionService:
    def __init__(self) -> None:
        self._voice_enabled = bool(settings.voice_input_enabled)
        self._provider_key = str(settings.voice_transcription_provider or "").strip().lower() or "openai"
        self._max_duration_seconds = max(5, int(settings.voice_max_duration_seconds))
        self._max_bytes = self._max_duration_seconds * MAX_BYTES_PER_SECOND

    @property
    def provider_key(self) -> str:
        return self._provider_key

    @property
    def max_duration_seconds(self) -> int:
        return self._max_duration_seconds

    def transcribe(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> TranscriptionResult:
        if not self._voice_enabled:
            raise TranscriptionFeatureDisabledError("Voice input is disabled")

        cleaned_name = str(filename or "").strip()
        if not cleaned_name:
            raise TranscriptionValidationError("Uploaded file name is missing")

        extension = Path(cleaned_name).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise TranscriptionValidationError("Unsupported audio file extension")

        normalized_content_type = str(content_type or "").split(";")[0].strip().lower()
        if normalized_content_type and normalized_content_type not in SUPPORTED_MIME_TYPES:
            raise TranscriptionValidationError("Unsupported audio content type")

        if not audio_bytes:
            raise TranscriptionValidationError("Audio payload is empty")
        if len(audio_bytes) > self._max_bytes:
            raise TranscriptionValidationError(
                f"Audio payload exceeds maximum allowed size for {self._max_duration_seconds} seconds",
            )

        provider = self._build_provider()
        return provider.transcribe(
            audio_bytes=audio_bytes,
            filename=cleaned_name,
            content_type=normalized_content_type or None,
        )

    def _build_provider(self):
        if self._provider_key == "openai":
            return OpenAITranscriptionProvider()
        raise TranscriptionProviderUnavailableError(
            f"Unsupported transcription provider '{self._provider_key}'",
        )
