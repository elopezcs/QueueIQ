import importlib
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BACKEND_ROOT = REPO_ROOT / "Chatbot" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if "app" not in sys.modules:
    sys.modules["app"] = importlib.import_module("Chatbot.backend.app")

from API.rag.routes import router as rag_router


class _FakeTranscriptionResult:
    def __init__(self, transcript: str, provider: str):
        self.transcript = transcript
        self.provider = provider


class _FakeTranscriptionService:
    def transcribe(self, *, audio_bytes: bytes, filename: str, content_type: str | None = None):
        assert audio_bytes
        return _FakeTranscriptionResult(
            transcript="I have had a cough for two days",
            provider="openai",
        )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(rag_router)
    return TestClient(app)


def test_voice_config_default_off(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_input_enabled", False)
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", False)
    client = _client()
    response = client.get("/rag/voice/config")
    assert response.status_code == 200
    body = response.json()
    assert body["voice_input_enabled"] is False
    assert body["voice_output_enabled"] is False


def test_voice_config_output_enabled_when_set(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_output_enabled", True)
    client = _client()
    response = client.get("/rag/voice/config")
    assert response.status_code == 200
    body = response.json()
    assert body["voice_output_enabled"] is True


def test_voice_transcribe_disabled_returns_controlled_error(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_input_enabled", False)
    client = _client()
    response = client.post(
        "/rag/chat/transcribe",
        files={"file": ("recording.webm", b"voice-bytes", "audio/webm")},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "FEATURE_DISABLED"


def test_voice_transcribe_success_when_enabled(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_input_enabled", True)
    monkeypatch.setattr("API.rag.routes.TranscriptionService", lambda: _FakeTranscriptionService())
    client = _client()
    response = client.post(
        "/rag/chat/transcribe",
        files={"file": ("recording.webm", b"voice-bytes", "audio/webm")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["provider"] == "openai"
    assert body["transcript"] == "I have had a cough for two days"


def test_voice_transcribe_invalid_file_type(monkeypatch):
    monkeypatch.setattr("API.rag.routes.settings.voice_input_enabled", True)
    client = _client()
    response = client.post(
        "/rag/chat/transcribe",
        files={"file": ("recording.txt", b"not-audio", "text/plain")},
    )
    assert response.status_code == 415
    body = response.json()
    assert body["error_code"] == "UNSUPPORTED_MEDIA_TYPE"
