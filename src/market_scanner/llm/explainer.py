import json
from collections.abc import Mapping, Sequence
from typing import Any

from market_scanner.llm.base import LLMProvider

_ALLOWED_FIELDS = {
    "symbol",
    "close",
    "lux_trend",
    "lux_strength",
    "lux_last_event",
    "smc_range_position_pct",
    "smc_rsi",
    "alignment",
    "adjusted_alignment",
    "market_state",
    "action_bucket",
    "consistency_score",
}

_SYSTEM_INSTRUCTION = """\
You are a financial analysis assistant.

Your task is to explain scanner results.

Rules:
- Do NOT give buy or sell recommendations.
- Do NOT invent data.
- Use ONLY the provided inputs.
- Focus on reasoning, signal quality and risk.
- Highlight contradictions between indicators.
- Be concise and structured.
- Treat scanner fields as source of truth."""

_USER_PROMPT_TEMPLATE = """\
Analyze the following assets:

{json_rows}

For each asset:

1. Summarize the current technical state.
2. Explain why it is classified this way.
3. Identify risks or contradictions.
4. Explain what would improve the setup.
5. Classify explanation confidence as low, medium or high.

Output format: {output_format}"""


def _sanitize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k in _ALLOWED_FIELDS}


def generate_explanations(
    rows: Sequence[Mapping[str, Any]],
    provider: LLMProvider,
    *,
    output_format: str = "markdown",
    max_tokens: int = 4000,
) -> str:
    sanitized = [_sanitize_row(r) for r in rows]
    json_rows = json.dumps(sanitized, indent=2, default=str)
    prompt = f"{_SYSTEM_INSTRUCTION}\n\n{_USER_PROMPT_TEMPLATE.format(json_rows=json_rows, output_format=output_format)}"
    return provider.generate(prompt, max_tokens=max_tokens)
