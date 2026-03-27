import hashlib
import math
from typing import Protocol

import requests

from Chatbot.backend.app.core.settings import settings


class EmbeddingAdapter(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class DeterministicHashEmbeddingAdapter:
    """
    Deterministic local fallback that avoids external dependencies.
    """

    def __init__(self, dimensions: int) -> None:
        self.dimensions = max(8, dimensions)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dimensions
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                weight = 1.0 + (digest[5] / 255.0)
                vec[idx] += sign * weight
            vectors.append(_normalize(vec))
        return vectors


class OllamaEmbeddingAdapter:
    def __init__(self, base_url: str | None = None, model_name: str | None = None) -> None:
        self.base_url = (base_url or settings.rag_ollama_base_url).rstrip("/")
        self.model_name = model_name or settings.rag_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            payload = {"model": self.model_name, "prompt": text}
            response = requests.post(f"{self.base_url}/api/embeddings", json=payload, timeout=45)
            response.raise_for_status()
            body = response.json()
            raw = body.get("embedding") or []
            out.append([float(v) for v in raw])
        return out


class OpenAICompatibleEmbeddingAdapter:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model_name: str | None = None) -> None:
        self.base_url = (base_url or settings.rag_openai_base_url).rstrip("/")
        self.api_key = api_key or settings.rag_openai_api_key
        self.model_name = model_name or settings.rag_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model_name, "input": texts}
        response = requests.post(f"{self.base_url}/embeddings", json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        body = response.json()
        data = body.get("data") or []
        data = sorted(data, key=lambda row: int(row.get("index", 0)))
        return [[float(v) for v in row.get("embedding") or []] for row in data]

