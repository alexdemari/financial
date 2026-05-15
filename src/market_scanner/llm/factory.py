from market_scanner.llm.base import LLMProvider


def get_llm_provider(name: str, model: str | None = None) -> LLMProvider:
    normalized = name.strip().lower()

    if normalized == "local":
        from market_scanner.llm.local_provider import LocalProvider

        return LocalProvider(model=model)

    if normalized == "openai":
        from market_scanner.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(model=model)

    if normalized == "anthropic":
        from market_scanner.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model)

    raise ValueError(
        f"Unsupported LLM provider: {name!r}. Choose from: local, openai, anthropic"
    )
