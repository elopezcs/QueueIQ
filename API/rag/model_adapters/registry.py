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


def _safe_model_key(name: str) -> str:
    key = name.strip().lower()
    return key.replace(":", "_").replace(".", "_").replace("-", "_")


def _load_model_specs() -> dict[str, ModelSpec]:
    raw_specs = settings.rag_model_specs or {}
    specs: dict[str, ModelSpec] = {}

    for key, config in raw_specs.items():
        if not isinstance(config, dict):
            continue
        provider = str(config.get("provider", "")).strip().lower()
        model_name = str(config.get("model_name", "")).strip()
        prompt_variant = str(config.get("prompt_variant", "default")).strip().lower() or "default"
        spec_key = str(config.get("key", key)).strip().lower() or _safe_model_key(model_name or key)
        if provider and model_name:
            specs[spec_key] = ModelSpec(
                key=spec_key,
                provider=provider,
                model_name=model_name,
                prompt_variant=prompt_variant,
            )

    if specs:
        return specs

    fallback_model = settings.rag_active_model.strip() or "gemma3:4b"
    fallback_key = _safe_model_key(fallback_model)
    return {
        fallback_key: ModelSpec(
            key=fallback_key,
            provider=settings.rag_model_provider.strip().lower() or "ollama",
            model_name=fallback_model,
            prompt_variant="default",
        )
    }


_MODEL_SPECS = _load_model_specs()


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
    if desired in _MODEL_SPECS:
        return _MODEL_SPECS[desired]
    for spec in _MODEL_SPECS.values():
        if spec.model_name.strip().lower() == desired:
            return spec
    return next(iter(_MODEL_SPECS.values()))


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

