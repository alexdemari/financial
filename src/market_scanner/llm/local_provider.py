class LocalProvider:
    def __init__(self, model: str | None = None):
        self.model = model or "local-stub"

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> str:
        return "LLM local provider not implemented."
