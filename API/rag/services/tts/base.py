from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class TTSResult:
    audio_bytes: bytes
    provider: str
    audio_format: str
    content_type: str


class TTSProvider(Protocol):
    provider_name: str

    def synthesize(self, *, text: str, language: Literal["en", "fr", "es"] | None = None) -> TTSResult:
        ...
