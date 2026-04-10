from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranscriptionResult:
    transcript: str
    provider: str


class TranscriptionProvider(Protocol):
    provider_name: str

    def transcribe(self, *, audio_bytes: bytes, filename: str, content_type: str | None = None) -> TranscriptionResult:
        ...
