from API.rag.model_adapters.providers import OpenAICompatibleAdapter, OllamaAdapter


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_ollama_adapter_parses_json(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return _DummyResponse({"response": '{"assistant_message":"hello","done":false}'})

    monkeypatch.setattr("API.rag.model_adapters.providers.requests.post", fake_post)
    adapter = OllamaAdapter(base_url="http://local")
    out = adapter.generate_structured(model_name="gemma3:4b", system_prompt="sys", user_prompt="usr")
    assert out["assistant_message"] == "hello"
    assert out["done"] is False


def test_openai_compatible_adapter_parses_json(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        return _DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"assistant_message":"ok","done":true}',
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("API.rag.model_adapters.providers.requests.post", fake_post)
    adapter = OpenAICompatibleAdapter(base_url="http://local/v1", api_key="x")
    out = adapter.generate_structured(model_name="qwen", system_prompt="sys", user_prompt="usr")
    assert out["assistant_message"] == "ok"
    assert out["done"] is True

