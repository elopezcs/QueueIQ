import logging

from openai import OpenAI

from Chatbot.backend.app.core.settings import settings

from .base import TranscriptionProvider, TranscriptionResult
from .errors import TranscriptionProviderFailureError, TranscriptionProviderUnavailableError

logger = logging.getLogger("queueiq.rag.transcription.openai")


class OpenAITranscriptionProvider(TranscriptionProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise TranscriptionProviderUnavailableError("OPENAI_API_KEY is not configured")
        self._client = OpenAI(api_key=settings.openai_api_key)

    def transcribe(self, *, audio_bytes: bytes, filename: str, content_type: str | None = None) -> TranscriptionResult:
        if not audio_bytes:
            raise TranscriptionProviderFailureError("Audio payload is empty")
        try:
            response = self._client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=(filename, audio_bytes, content_type or "application/octet-stream"),
            )
            transcript = str(getattr(response, "text", "") or "").strip()
            if not transcript:
                raise TranscriptionProviderFailureError("Transcription provider returned an empty transcript")
            return TranscriptionResult(
                transcript=transcript,
                provider=self.provider_name,
            )
        except TranscriptionProviderFailureError:
            raise
        except Exception as exc:
            logger.exception("OpenAI transcription failed")
            raise TranscriptionProviderFailureError("Transcription request failed") from exc
