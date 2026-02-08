import json
import logging
from typing import Any

from openai import OpenAI
from app.core.settings import settings

logger = logging.getLogger("queueiq.llm")


class LLMClient:
    """
    Centralized LLM client wrapper.

    Uses OpenAI Responses API style:
    - client.responses.create(...)
    - response.output_text
    """

    def __init__(self) -> None:
        self._enabled = bool(settings.openai_api_key)
        self._client = OpenAI(api_key=settings.openai_api_key) if self._enabled else None
        self._model = settings.openai_model

    @property
    def enabled(self) -> bool:
        return self._enabled

    def generate_json(self, prompt: str) -> dict[str, Any]:
        """
        Returns parsed JSON dict from the model.
        Falls back to a deterministic stub if OPENAI_API_KEY is not set.
        """
        if not self._enabled:
            logger.warning("OPENAI_API_KEY not set. Using stubbed LLM response.")
            return {"_stub": True}

        assert self._client is not None

        resp = self._client.responses.create(
            model=self._model,
            input=prompt,
        )

        text = (resp.output_text or "").strip()
        if not text:
            raise ValueError("LLM returned empty response")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise ValueError(f"LLM returned non-JSON output: {text[:200]}")
