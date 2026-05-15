from typing import Protocol


class LLMProvider(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> str:
        ...
