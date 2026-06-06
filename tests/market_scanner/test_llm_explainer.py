import pytest

from market_scanner.llm.explainer import generate_explanations, _sanitize_row
from market_scanner.llm.factory import get_llm_provider


class FakeProvider:
    def generate(self, prompt: str, **kwargs) -> str:
        return "mocked response"


class PromptCapturingProvider:
    def __init__(self):
        self.last_prompt: str = ""

    def generate(self, prompt: str, **kwargs) -> str:
        self.last_prompt = prompt
        return "captured"


# ---------------------------------------------------------------------------
# generate_explanations
# ---------------------------------------------------------------------------


def test_generate_explanations_calls_provider_and_returns_response() -> None:
    rows = [
        {"symbol": "AAPL", "market_state": "pullback", "action_bucket": "candidate"}
    ]
    result = generate_explanations(rows, FakeProvider())
    assert result == "mocked response"


def test_prompt_includes_expected_symbols() -> None:
    provider = PromptCapturingProvider()
    rows = [
        {"symbol": "NVDA", "market_state": "extended", "action_bucket": "watchlist"},
        {"symbol": "AAPL", "market_state": "pullback", "action_bucket": "candidate"},
    ]
    generate_explanations(rows, provider)
    assert "NVDA" in provider.last_prompt
    assert "AAPL" in provider.last_prompt


def test_prompt_includes_required_scanner_fields() -> None:
    provider = PromptCapturingProvider()
    rows = [
        {
            "symbol": "MSFT",
            "market_state": "range",
            "adjusted_alignment": "bullish_aligned",
            "action_bucket": "candidate",
            "consistency_score": 4,
        }
    ]
    generate_explanations(rows, provider)
    assert "market_state" in provider.last_prompt
    assert "adjusted_alignment" in provider.last_prompt
    assert "action_bucket" in provider.last_prompt


def test_prompt_does_not_include_raw_ohlc_fields() -> None:
    provider = PromptCapturingProvider()
    rows = [
        {
            "symbol": "TSLA",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "volume": 1_000_000,
            "market_state": "pullback",
            "action_bucket": "candidate",
        }
    ]
    generate_explanations(rows, provider)
    # Check JSON key form — "open": / "high": etc. are stripped by sanitize
    assert '"open":' not in provider.last_prompt
    assert '"high":' not in provider.last_prompt
    assert '"low":' not in provider.last_prompt
    assert '"volume":' not in provider.last_prompt


def test_sanitize_row_strips_disallowed_fields() -> None:
    row = {
        "symbol": "X",
        "market_state": "pullback",
        "open": 50.0,
        "high": 55.0,
        "low": 48.0,
        "volume": 500_000,
        "some_internal_id": 999,
    }
    result = _sanitize_row(row)
    assert "symbol" in result
    assert "market_state" in result
    assert "open" not in result
    assert "volume" not in result
    assert "some_internal_id" not in result


# ---------------------------------------------------------------------------
# factory
# ---------------------------------------------------------------------------


def test_factory_returns_local_provider_for_local() -> None:
    from market_scanner.llm.local_provider import LocalProvider

    provider = get_llm_provider("local")
    assert isinstance(provider, LocalProvider)


def test_factory_raises_for_unsupported_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_provider("unknown_provider")


def test_factory_returns_anthropic_provider_for_anthropic() -> None:
    from market_scanner.llm.anthropic_provider import AnthropicProvider

    provider = get_llm_provider("anthropic")
    assert isinstance(provider, AnthropicProvider)


def test_factory_returns_openai_provider_for_openai() -> None:
    from market_scanner.llm.openai_provider import OpenAIProvider

    provider = get_llm_provider("openai")
    assert isinstance(provider, OpenAIProvider)


# ---------------------------------------------------------------------------
# provider error handling (no network required)
# ---------------------------------------------------------------------------


def test_openai_provider_fails_clearly_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from market_scanner.llm.openai_provider import OpenAIProvider

    provider = OpenAIProvider()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.generate("test")


def test_anthropic_provider_fails_clearly_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from market_scanner.llm.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider()
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        provider.generate("test")


# ---------------------------------------------------------------------------
# report writer
# ---------------------------------------------------------------------------


def test_report_writer_writes_md_for_markdown(tmp_path) -> None:
    from market_scanner.report_writer import write_llm_report

    path = write_llm_report("# Report", output_format="markdown", output_dir=tmp_path)
    assert path.suffix == ".md"
    assert path.read_text() == "# Report"


def test_report_writer_writes_json_for_json(tmp_path) -> None:
    from market_scanner.report_writer import write_llm_report

    path = write_llm_report(
        '{"key": "value"}', output_format="json", output_dir=tmp_path
    )
    assert path.suffix == ".json"
    assert path.read_text() == '{"key": "value"}'
