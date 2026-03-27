from typing import Any

from API.rag.model_adapters.base import LocalModelAdapter, ModelSpec
from API.rag.model_adapters.embeddings import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingAdapter,
    OllamaEmbeddingAdapter,
    OpenAICompatibleEmbeddingAdapter,
)
from API.rag.model_adapters.providers import OllamaAdapter, OpenAICompatibleAdapter
from API.rag.db import execute, fetch_all, rag_db_enabled
from Chatbot.backend.app.core.settings import settings


_MODEL_SPECS = {
    "gemma3_4b": ModelSpec(
        key="gemma3_4b",
        provider="ollama",
        model_name="gemma3:4b",
        prompt_variant="gemma",
    ),
    "qwen2_5_7b_instruct": ModelSpec(
        key="qwen2_5_7b_instruct",
        provider="ollama",
        model_name="qwen2.5:7b-instruct",
        prompt_variant="qwen",
    ),
}


def _provider_for(provider_key: str) -> LocalModelAdapter:
    key = provider_key.strip().lower()
    if key == "openai_compatible":
        return OpenAICompatibleAdapter()
    return OllamaAdapter()


def list_models() -> list[dict[str, Any]]:
    active = settings.rag_active_model
    out = []
    for key, spec in _MODEL_SPECS.items():
        out.append(
            {
                "key": key,
                "provider": spec.provider,
                "model_name": spec.model_name,
                "prompt_variant": spec.prompt_variant,
                "active": key == active,
            }
        )
    return out


def active_model() -> ModelSpec:
    desired = settings.rag_active_model.strip().lower()
    return _MODEL_SPECS.get(desired, _MODEL_SPECS["gemma3_4b"])


def active_adapter() -> LocalModelAdapter:
    provider = settings.rag_model_provider.strip().lower()
    if provider in {"ollama", "openai_compatible"}:
        return _provider_for(provider)
    return _provider_for(active_model().provider)


def persist_model_registry() -> None:
    if not rag_db_enabled():
        return
    active = active_model().key
    for spec in _MODEL_SPECS.values():
        execute(
            """
            INSERT INTO rag.model_configs(model_key, provider, model_name, prompt_variant, is_active, metadata_json)
            VALUES(%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (model_key) DO UPDATE
              SET provider=EXCLUDED.provider,
                  model_name=EXCLUDED.model_name,
                  prompt_variant=EXCLUDED.prompt_variant,
                  is_active=EXCLUDED.is_active
            """,
            (spec.key, spec.provider, spec.model_name, spec.prompt_variant, spec.key == active, "{}"),
        )


def db_models_or_default() -> list[dict[str, Any]]:
    if not rag_db_enabled():
        return list_models()
    rows = fetch_all(
        "SELECT model_key, provider, model_name, prompt_variant, is_active FROM rag.model_configs ORDER BY model_key"
    )
    if not rows:
        persist_model_registry()
        rows = fetch_all(
            "SELECT model_key, provider, model_name, prompt_variant, is_active FROM rag.model_configs ORDER BY model_key"
        )
    return [
        {
            "key": row["model_key"],
            "provider": row["provider"],
            "model_name": row["model_name"],
            "prompt_variant": row["prompt_variant"],
            "active": bool(row["is_active"]),
        }
        for row in rows
    ]


def active_embedding_adapter() -> EmbeddingAdapter:
    provider = settings.rag_model_provider.strip().lower()
    if provider == "openai_compatible":
        adapter: EmbeddingAdapter = OpenAICompatibleEmbeddingAdapter()
    elif provider == "ollama":
        adapter = OllamaEmbeddingAdapter()
    else:
        adapter = DeterministicHashEmbeddingAdapter(settings.rag_vector_dimensions)
    return adapter


def embed_text(text: str) -> list[float]:
    if not settings.rag_enable_embeddings:
        return DeterministicHashEmbeddingAdapter(settings.rag_vector_dimensions).embed([text])[0]
    try:
        vec = active_embedding_adapter().embed([text])[0]
        if vec:
            return vec
    except Exception:
        pass
    return DeterministicHashEmbeddingAdapter(settings.rag_vector_dimensions).embed([text])[0]

