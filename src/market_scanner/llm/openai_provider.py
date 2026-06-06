import os


class OpenAIProvider:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when using the OpenAI LLM provider"
            )

        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "openai package is not installed. Run: uv add openai"
            ) from exc

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
