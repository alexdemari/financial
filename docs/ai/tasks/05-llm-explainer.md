# Task: Integrate Optional LLM Explainer into `market_scanner` (LLM-Agnostic)

You are working on a local-first Python financial analysis system.

---
status: planned
last-updated: 2026-04
target: market_scanner (migrated from options_tech_scanner)
providers: openai, anthropic, local
---

## Context

The system architecture is:

- `stock_data_manager` → local OHLC data
- `trading_indicators` → reusable indicator/model logic such as Lux and SMC
- `stock_analyzer` → single-symbol analysis
- `market_scanner` → multi-symbol scan, eligibility, ranking and reporting

The system is:

- local-first
- synchronous
- CLI-driven
- file-based
- deterministic by default

Scanner V2 now includes:

- `market_state`
- `adjusted_alignment`
- `action_bucket`

These fields represent the local decision layer and must remain fully deterministic.

---

## Goal

Add an optional LLM-based explanation layer that:

- consumes scanner output after the scan is complete
- analyzes only the top-N rows
- generates a human-readable report
- does not affect ranking, scoring or decision logic
- supports multiple LLM providers, such as OpenAI, local models or future providers
- fails gracefully if the provider is unavailable

The LLM must act as an **explainer**, not as the scanner decision engine.

---

## Non-Goals

Do not:

- call the LLM inside the core scan loop
- use the LLM for ranking or scoring
- replace `market_state`, `alignment`, `adjusted_alignment` or `action_bucket`
- introduce async, queues, Redis, databases or external infrastructure
- make scanner execution dependent on LLM availability
- send full OHLC history to the LLM
- send sensitive local files to the LLM
- modify unrelated scanner flows such as the existing BULL_PUT_SPREAD scanner

---

## High-Level Architecture

```text
scan.py (local execution)
        ↓
scanner rows with market_state, adjusted_alignment, action_bucket
        ↓
top-N selection
        ↓
optional LLM explainer
        ↓
markdown or JSON report saved locally
```

The scanner must continue to work exactly as before when the LLM feature is disabled.

---

## CLI Design

Extend the existing scanner CLI with optional flags:

```bash
--llm-explain
--llm-provider <provider_name>
--llm-model <model_name>
--llm-top-n <int>
--llm-output-format markdown|json
```

Suggested defaults:

```text
--llm-explain: false
--llm-provider: value from LLM_PROVIDER env var, fallback to anthropic
--llm-model: value from LLM_MODEL env var, provider-specific fallback allowed
  (openai default: gpt-4o-mini | anthropic default: claude-haiku-4-5)
--llm-top-n: same as --top
--llm-output-format: markdown
```

Example with OpenAI:

```bash
python -m market_scanner.scan \
  --universe data/universe.json \
  --top 10 \
  --llm-explain \
  --llm-provider openai \
  --llm-model gpt-4o-mini
```

Example with local provider stub:

```bash
python -m market_scanner.scan \
  --top 5 \
  --llm-explain \
  --llm-provider local
```

---

## Environment Configuration

Use environment variables for provider configuration:

```bash
# OpenAI
OPENAI_API_KEY=...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Anthropic
ANTHROPIC_API_KEY=...
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5
```

Provider-specific variables are allowed, but must not be hardcoded in the scanner.

The scanner should not require these variables unless `--llm-explain` is enabled.

---

## Module Structure

Create a small provider-agnostic LLM package inside `market_scanner`:

```text
src/market_scanner/llm/
    __init__.py
    base.py
    openai_provider.py
    anthropic_provider.py
    local_provider.py
    factory.py
    explainer.py
```

Keep this minimal. Do not introduce a dependency injection framework.

---

## 1. Base Interface

File:

```text
src/market_scanner/llm/base.py
```

Define a simple provider protocol:

```python
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
```

The rest of the scanner should depend only on this protocol, not on provider-specific SDKs.

---

## 2. Provider Factory

File:

```text
src/market_scanner/llm/factory.py
```

Implement:

```python
from market_scanner.llm.base import LLMProvider


def get_llm_provider(name: str, model: str | None = None) -> LLMProvider:
    ...
```

Supported providers for this task:

- `openai`
- `anthropic`
- `local`

Behavior:

- normalize provider name using lowercase
- raise a clear `ValueError` for unsupported providers
- do not import provider SDKs unless that provider is selected

Example behavior:

```python
provider = get_llm_provider("openai", "gpt-4o-mini")
provider = get_llm_provider("anthropic", "claude-haiku-4-5")
```

---

## 3. OpenAI Provider

File:

```text
src/market_scanner/llm/openai_provider.py
```

Requirements:

- use the official OpenAI Python client if available in the project
- read API key from `OPENAI_API_KEY`
- do not hardcode the model
- fail gracefully with a clear error if not configured
- keep the implementation isolated from scanner logic

Example structure:

```python
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
            raise RuntimeError("OPENAI_API_KEY is required when using the OpenAI LLM provider")

        # Use the official OpenAI client here.
        # Return only the response text.
        ...
```

Recommended behavior:

- provider may raise exceptions
- scanner integration must catch those exceptions and continue

---

## 4. Anthropic Provider

File:

```text
src/market_scanner/llm/anthropic_provider.py
```

Requirements:

- use the official `anthropic` Python SDK
- read API key from `ANTHROPIC_API_KEY`
- do not hardcode the model — default to `claude-haiku-4-5` (fast and cheap)
- fail gracefully with a clear error if not configured
- keep the implementation isolated from scanner logic

Example structure:

```python
import os


class AnthropicProvider:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("LLM_MODEL") or "claude-haiku-4-5"

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required when using the Anthropic LLM provider"
            )

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
```

Recommended behavior:

- provider may raise exceptions
- scanner integration must catch those exceptions and continue

---

## 5. Local Provider Stub

File:

```text
src/market_scanner/llm/local_provider.py
```

Initial behavior:

```python
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
```

Purpose:

- keep the architecture extensible
- allow tests without network
- allow future integration with Ollama, LM Studio or another local runtime

Do not implement a real local runtime in this task.

---

## 6. Explainer Module

File:

```text
src/market_scanner/llm/explainer.py
```

Implement:

```python
from collections.abc import Mapping, Sequence
from typing import Any

from market_scanner.llm.base import LLMProvider


def generate_explanations(
    rows: Sequence[Mapping[str, Any]],
    provider: LLMProvider,
    *,
    output_format: str = "markdown",
) -> str:
    ...
```

Responsibilities:

- sanitize rows before sending to the provider
- build a deterministic prompt
- call provider once for the whole top-N set
- return provider output as string

Do not write files inside `generate_explanations`. File writing should remain in scanner/report integration.

---

## 7. Input Sent to the LLM

Only send top-N rows.

Each row should include only compact scanner fields:

```json
{
  "symbol": "AFRM",
  "close": 62.98,
  "lux_trend": "BULLISH",
  "lux_strength": "STRONG",
  "lux_last_event": "SELL",
  "smc_range_position_pct": 78.4,
  "smc_rsi": 64.7,
  "alignment": "bullish_aligned",
  "adjusted_alignment": "bullish_watchlist",
  "market_state": "extended",
  "action_bucket": "watchlist",
  "consistency_score": 1
}
```

Do not send:

- raw OHLC history
- full CSV content
- universe file
- account information
- position sizing
- brokerage account data
- API keys
- file paths unless needed for debugging

---

## 8. Prompt Design

Create a constrained prompt.

The prompt should make clear that the LLM explains the scanner output and must not invent missing data.

Recommended system instruction inside the prompt:

```text
You are a financial analysis assistant.

Your task is to explain scanner results.

Rules:
- Do NOT give buy or sell recommendations.
- Do NOT invent data.
- Use ONLY the provided inputs.
- Focus on reasoning, signal quality and risk.
- Highlight contradictions between indicators.
- Be concise and structured.
- Treat scanner fields as source of truth.
```

Recommended user prompt template:

```text
Analyze the following assets:

{json_rows}

For each asset:

1. Summarize the current technical state.
2. Explain why it is classified this way.
3. Identify risks or contradictions.
4. Explain what would improve the setup.
5. Classify explanation confidence as low, medium or high.

Output format: {output_format}
```

---

## 9. Markdown Output Format

Markdown is the default.

Expected style:

```markdown
# Scanner LLM Explanation

## AFRM

- **State:** extended bullish
- **Scanner classification:** bullish_aligned → bullish_watchlist
- **Interpretation:** strong trend, but current location is extended.
- **Risk:** recent SELL event conflicts with bullish trend.
- **What would improve the setup:** pullback toward mid-range with stabilization.
- **Confidence:** medium
```

The report must not say:

- “Buy AFRM”
- “Sell GILD”
- “This is financial advice”
- “Guaranteed setup”

---

## 10. JSON Output Format

If `--llm-output-format json` is selected, request output like:

```json
[
  {
    "symbol": "AFRM",
    "state": "extended bullish",
    "scanner_classification": "bullish_aligned -> bullish_watchlist",
    "summary": "Strong bullish trend, but current range position suggests extension.",
    "risks": ["Recent SELL event conflicts with bullish trend"],
    "what_would_improve": ["Pullback toward mid-range", "Stabilization after pullback"],
    "confidence": "medium"
  }
]
```

Validation of LLM JSON can be lightweight in this task.

Do not make JSON parsing mandatory unless the project already has a pattern for that.

---

## 11. Integration with `scan.py`

Add the LLM step after:

- scanner rows are computed
- V2 fields are computed
- top-N selection is available
- CSV writing remains unaffected

Pseudo-flow:

```python
if args.llm_explain:
    try:
        provider = get_llm_provider(args.llm_provider, args.llm_model)

        llm_rows = top_rows[: args.llm_top_n]

        explanations = generate_explanations(
            llm_rows,
            provider,
            output_format=args.llm_output_format,
        )

        report_path = write_llm_report(
            explanations,
            output_format=args.llm_output_format,
        )

        print(f"LLM explanation report written to: {report_path}")

    except Exception as exc:
        print(f"WARNING: LLM explanation skipped: {exc}")
```

Important:

- catch broad provider errors at the integration boundary
- do not fail the scan because of LLM issues
- do not alter CSV output if LLM fails

---

## 12. Output File

Save reports under:

```text
reports/
```

Suggested filenames:

```text
scanner_llm_report_<timestamp>.md
scanner_llm_report_<timestamp>.json
```

Timestamp format suggestion:

```text
YYYYMMDD_HHMMSS
```

Example:

```text
reports/scanner_llm_report_20260424_083000.md
```

---

## 13. Optional Report Writer Helper

If consistent with current project style, add a small helper to `report_writer.py` or a new file.

Example:

```python
from pathlib import Path
from datetime import datetime


def write_llm_report(content: str, *, output_format: str, output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "json" if output_format == "json" else "md"
    path = output_dir / f"scanner_llm_report_{timestamp}.{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
```

Keep this helper simple.

---

## 14. Error Handling

If any of these happen:

- API key missing
- provider not found
- provider SDK missing
- network failure
- model error
- timeout
- invalid provider response

Then:

- print a warning
- skip LLM report generation
- continue scanner execution
- keep CSV output intact
- exit code should remain success if scanner itself succeeded

Example warning:

```text
WARNING: LLM explanation skipped: OPENAI_API_KEY is required when using the OpenAI LLM provider
```

---

## 15. Tests

Add:

```text
tests/market_scanner/test_llm_explainer.py
```

Test with a fake provider:

```python
class FakeProvider:
    def generate(self, prompt: str, **kwargs) -> str:
        return "mocked response"
```

Required tests:

1. `generate_explanations` calls provider and returns response.
2. Prompt includes expected symbols.
3. Prompt includes `market_state`, `adjusted_alignment` and `action_bucket`.
4. Prompt does not include raw OHLC fields.
5. Factory returns local provider for `local`.
6. Factory raises clear error for unsupported provider.
7. OpenAI provider fails clearly when API key is missing.
8. Anthropic provider fails clearly when API key is missing.
9. Factory returns anthropic provider for `anthropic`.
10. Report writer writes `.md` when markdown is selected.
11. Report writer writes `.json` when json is selected.

Do not make tests require network access.

---

## 16. Acceptance Criteria

Run:

```bash
uv run pytest tests/market_scanner
```

If using ruff in the project:

```bash
uv run ruff check src/market_scanner tests/market_scanner
```

Functional acceptance:

- scanner runs normally without `--llm-explain`
- scanner runs with `--llm-explain --llm-provider local`
- scanner can select provider through CLI
- scanner can select model through CLI
- CSV output is unchanged
- LLM report is generated only when flag is enabled
- no network call occurs during normal scan
- LLM failure does not break scan

---

## 17. README Update

Update only the relevant scanner README section.

Document:

- `--llm-explain`
- `--llm-provider`
- `--llm-model`
- `--llm-top-n`
- `--llm-output-format`
- required environment variables
- warning that LLM output is explanatory only

Add a short example:

```bash
python -m market_scanner.scan \
  --top 10 \
  --llm-explain \
  --llm-provider openai \
  --llm-model gpt-4o-mini
```

---

## 18. Design Constraints

Keep the implementation:

- local-first by default
- synchronous
- file-based
- CLI-driven
- optional
- deterministic unless LLM flag is enabled
- easy to test
- easy to reason about

Do not introduce:

- async
- queues
- Redis
- database
- workflow engine
- background workers
- distributed architecture
- large refactor

---

## 19. Key Architectural Principle

The system must:

```text
decide locally
explain optionally
```

LLM is:

- an analyst
- a report generator
- a reasoning assistant over already computed fields

LLM is not:

- the decision engine
- the scorer
- the ranking engine
- a source of market data

---

## 20. Suggested Execution Order

1. Create `llm/base.py`.
2. Create `llm/local_provider.py`.
3. Create `llm/openai_provider.py`.
4. Create `llm/anthropic_provider.py`.
5. Create `llm/factory.py`.
6. Create `llm/explainer.py`.
7. Add report writer helper if needed.
8. Add CLI flags in `scan.py`.
9. Integrate post-scan LLM report generation.
10. Add tests.
11. Update README.
12. Run pytest and ruff.

---

## Final Note

This feature is successful if:

- scanner output remains deterministic
- LLM usage is opt-in
- decision logic remains local
- explanation quality improves user decision-making
- LLM failure has zero impact on core scanner execution

Failure condition:

```text
LLM becomes required for decisions.
```
