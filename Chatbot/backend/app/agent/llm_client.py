import json
import logging
import re
from typing import Any

from openai import OpenAI
from app.core.settings import settings

logger = logging.getLogger("queueiq.llm")


def _strip_code_fences(text: str) -> str:
    """
    Removes Markdown code fences like:
      ```json
      {...}
      ```
    or:
      ```
      {...}
      ```
    """
    t = text.strip()

    if not t.startswith("```"):
        return t

    lines = t.splitlines()

    # Drop the opening fence line (``` or ```json)
    if lines and lines[0].startswith("```"):
        lines = lines[1:]

    t = "\n".join(lines).strip()

    # Drop the closing fence if present
    if t.endswith("```"):
        t = t[:-3].strip()

    return t


def _extract_first_json_object(text: str) -> str | None:
    """
    Extracts the first {...} JSON object found in the text.
    Heuristic fallback for common LLM formatting mistakes.
    """
    match = re.search(r"\{.*\}", text.strip(), flags=re.DOTALL)
    if match:
        return match.group(0).strip()
    return None


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

        This method is defensive against common LLM formatting issues, such as
        wrapping JSON in Markdown code fences (```json ... ```).
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

        # 1) Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2) Strip Markdown code fences and try again
        cleaned = _strip_code_fences(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3) Extract first JSON object from the cleaned text and try again
        extracted = _extract_first_json_object(cleaned)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass

        raise ValueError(f"LLM returned non-JSON output: {text[:200]}")