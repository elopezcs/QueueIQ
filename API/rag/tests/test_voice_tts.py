import importlib
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from API.rag.services.tts.base import TTSResult
from API.rag.services.tts.errors import TTSProviderFailureError
from API.rag.services.tts.openai_provider import OpenAITTSProvider

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BACKEND_ROOT = REPO_ROOT / "Chatbot" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if "app" not in sys.modules:
    sys.modules["app"] = importlib.import_module("Chatbot.backend.app")

from API.rag.routes import router as rag_router


class _FakeTTSServiceSuccess:
    def synthesize(self, *, text: str, language: Literal["en", "fr", "es"] | None = None) -> TTSResult:
        assert text
        return TTSResult(
            audio_bytes=b"fake-mp3-audio",
            provider="openai",
            audio_format="mp3",
            content_type="audio/mpeg",
        )


class _FakeTTSServiceFailure:
    def synthesize(self, *, text: str, language: Literal["en", "fr", "es"] | None = None) -> TTSResult:
        raise TTSProviderFailureError("Text-to-speech request failed")


class _FakeTTSServiceCapture:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def synthesize(self, *, text: str, language: Literal["en", "fr", "es"] | None = None) -> TTSResult:
        self.calls.append({"text": text, "language": language})
        return TTSResult(
            audio_bytes=b"fake-mp3-audio",
            provider="openai",
            audio_format="mp3",
            content_type="audio/mpeg",
        )


class _DummyOpenAIResponse:
    def __init__(self, content: bytes = b"dummy-audio") -> None:
        self.content = content


class _DummySpeechAPI:
    def __init__(self) -> None:
        self.last_payload: dict | None = None

    def create(self, **kwargs):
        self.last_payload = kwargs
        return _DummyOpenAIResponse()


class _DummyOpenAIAudio:
    def __init__(self) -> None:
        self.speech = _DummySpeechAPI()


class _DummyOpenAIClient:
    def __init__(self) -> None:
        self.audio = _DummyOpenAIAudio()


class _DummyOpenAI:
    last_instance = None

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.audio = _DummyOpenAIAudio()
        _DummyOpenAI.last_instance = self


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(rag_router)
    return TestClient(app)


def test_voice_config_exposes_output_provider(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "openai")
    client = _client()
    response = client.get("/rag/voice/config")
    assert response.status_code == 200
    body = response.json()
    assert body["voice_output_enabled"] is True
    assert body["voice_output_provider"] == "openai"


def test_voice_config_invalid_output_provider_falls_back_to_system(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "invalid-provider")
    client = _client()
    response = client.get("/rag/voice/config")
    assert response.status_code == 200
    body = response.json()
    assert body["voice_output_provider"] == "system"


def test_voice_tts_disabled_returns_controlled_error(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", False)
    client = _client()
    response = client.post("/rag/chat/tts", json={"text": "hello"})
    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "FEATURE_DISABLED"


def test_voice_tts_system_provider_returns_controlled_unavailable(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "system")
    client = _client()
    response = client.post("/rag/chat/tts", json={"text": "hello"})
    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "TTS_UNAVAILABLE"


def test_voice_tts_rejects_empty_text(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "openai")
    client = _client()
    response = client.post("/rag/chat/tts", json={"text": ""})
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] in {"MISSING_FIELD", "INVALID_TEXT"}


def test_voice_tts_openai_success_returns_audio(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "openai")
    monkeypatch.setattr("API.rag.routes.TTSService", lambda: _FakeTTSServiceSuccess())
    client = _client()
    response = client.post("/rag/chat/tts", json={"text": "hello"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.content == b"fake-mp3-audio"


def test_voice_tts_openai_failure_is_controlled(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "openai")
    monkeypatch.setattr("API.rag.routes.TTSService", lambda: _FakeTTSServiceFailure())
    client = _client()
    response = client.post("/rag/chat/tts", json={"text": "hello"})
    assert response.status_code == 502
    body = response.json()
    assert body["error_code"] == "TTS_FAILED"


def test_voice_tts_accepts_preferred_language_and_forwards_to_service(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "openai")
    capture_service = _FakeTTSServiceCapture()
    monkeypatch.setattr("API.rag.routes.TTSService", lambda: capture_service)
    client = _client()
    response = client.post("/rag/chat/tts", json={"text": "bonjour", "preferred_language": "fr"})
    assert response.status_code == 200
    assert capture_service.calls[-1] == {"text": "bonjour", "language": "fr"}


def test_voice_tts_allows_missing_preferred_language(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_provider", "openai")
    capture_service = _FakeTTSServiceCapture()
    monkeypatch.setattr("API.rag.routes.TTSService", lambda: capture_service)
    client = _client()
    response = client.post("/rag/chat/tts", json={"text": "hello"})
    assert response.status_code == 200
    assert capture_service.calls[-1] == {"text": "hello", "language": None}


def _configure_openai_tts_settings(monkeypatch, instructions: str):
    monkeypatch.setattr("API.rag.services.tts.openai_provider.settings.openai_api_key", "test-key")
    monkeypatch.setattr("API.rag.services.tts.openai_provider.settings.openai_tts_model", "gpt-4o-mini-tts")
    monkeypatch.setattr("API.rag.services.tts.openai_provider.settings.openai_tts_voice", "coral")
    monkeypatch.setattr("API.rag.services.tts.openai_provider.settings.openai_tts_instructions", instructions)
    monkeypatch.setattr("API.rag.services.tts.openai_provider.settings.openai_tts_audio_format", "mp3")
    monkeypatch.setattr("API.rag.services.tts.openai_provider.settings.openai_tts_speed", 1.0)


def test_openai_provider_appends_language_hint_to_instructions(monkeypatch):
    _configure_openai_tts_settings(monkeypatch, instructions="Use a calm tone.")
    monkeypatch.setattr("API.rag.services.tts.openai_provider.OpenAI", _DummyOpenAI)
    provider = OpenAITTSProvider()
    result = provider.synthesize(text="Bonjour", language="fr")
    assert result.audio_bytes == b"dummy-audio"
    payload = _DummyOpenAI.last_instance.audio.speech.last_payload
    assert payload is not None
    assert payload.get("instructions") == "Use a calm tone. Speak naturally in French."


def test_openai_provider_keeps_base_instructions_without_language(monkeypatch):
    _configure_openai_tts_settings(monkeypatch, instructions="Use a calm tone.")
    monkeypatch.setattr("API.rag.services.tts.openai_provider.OpenAI", _DummyOpenAI)
    provider = OpenAITTSProvider()
    result = provider.synthesize(text="Hello")
    assert result.audio_bytes == b"dummy-audio"
    payload = _DummyOpenAI.last_instance.audio.speech.last_payload
    assert payload is not None
    assert payload.get("instructions") == "Use a calm tone."
