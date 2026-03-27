import json
import re
from typing import Any

import requests

from API.rag.model_adapters.base import LocalModelAdapter
from Chatbot.backend.app.core.settings import settings


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {"assistant_message": str(parsed)}
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {"assistant_message": str(parsed)}
            except Exception:
                pass
    return {"assistant_message": cleaned}


class OllamaAdapter(LocalModelAdapter):
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.rag_ollama_base_url).rstrip("/")

    def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": model_name,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "format": "json",
        }
        response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=45)
        response.raise_for_status()
        body = response.json()
        raw_text = str(body.get("response") or "").strip()
        return _parse_json_response(raw_text)


class OpenAICompatibleAdapter(LocalModelAdapter):
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or settings.rag_openai_base_url).rstrip("/")
        self.api_key = api_key or settings.rag_openai_api_key

    def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices") or []
        message = (choices[0] or {}).get("message", {}) if choices else {}
        raw_text = str(message.get("content") or "").strip()
        return _parse_json_response(raw_text)

