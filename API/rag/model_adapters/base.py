from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str
    model_name: str
    prompt_variant: str


class LocalModelAdapter(Protocol):
    def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        ...

