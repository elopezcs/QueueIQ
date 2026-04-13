from typing import Literal

from Chatbot.backend.app.core.settings import settings

from .base import TTSResult
from .errors import TTSFeatureDisabledError, TTSProviderUnavailableError, TTSValidationError
from .openai_provider import OpenAITTSProvider

_SUPPORTED_OUTPUT_PROVIDERS = {"system", "openai"}


class TTSService:
    def __init__(self) -> None:
        self._voice_enabled = bool(settings.voice_output_enabled)
        raw_provider = str(settings.voice_output_provider or "").strip().lower()
        self._provider_key = raw_provider if raw_provider in _SUPPORTED_OUTPUT_PROVIDERS else "system"

    @property
    def provider_key(self) -> str:
        return self._provider_key

    def synthesize(self, *, text: str, language: Literal["en", "fr", "es"] | None = None) -> TTSResult:
        if not self._voice_enabled:
            raise TTSFeatureDisabledError("Voice output is disabled")

        cleaned_text = str(text or "").strip()
        if not cleaned_text:
            raise TTSValidationError("text is required and cannot be empty")
        if len(cleaned_text) > 8000:
            raise TTSValidationError("text exceeds maximum supported length")

        if self._provider_key != "openai":
            raise TTSProviderUnavailableError(
                f"Provider '{self._provider_key}' does not require backend synthesis",
            )

        normalized_language = language if language in {"en", "fr", "es"} else None
        provider = OpenAITTSProvider()
        return provider.synthesize(text=cleaned_text, language=normalized_language)
