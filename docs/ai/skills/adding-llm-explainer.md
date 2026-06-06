---
name: adding-llm-explainer
description: >
  Adds LLM-generated explanations to market_scanner output. Use when implementing
  the --explain flag in scan.py, building market_scanner/llm/explainer.py,
  or integrating Anthropic API as a post-scan opt-in step.
---

# Adding LLM Explainer

## Structure

```
src/market_scanner/llm/
  __init__.py
  explainer.py    ← public interface
  prompts.py      ← prompt templates per action_bucket
```

## Core interface

```python
# explainer.py
import os
from anthropic import Anthropic

def explain_row(row: dict, model: str = "claude-haiku-4-5") -> str:
    """
    Returns a 2-3 sentence explanation for a scanner row's action_bucket.
    Returns empty string on any failure — never raises.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        client = Anthropic(api_key=api_key)
        prompt = build_prompt(row)
        response = client.messages.create(
            model=model,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception:
        return ""
```

## Prompt pattern

```python
# prompts.py
def build_prompt(row: dict) -> str:
    return f"""Symbol: {row['symbol']}
Action: {row['action_bucket']}
Alignment: {row['adjusted_alignment']}
Market state: {row['market_state']}
Lux role: {row['lux_role']} | SMC role: {row['smc_role']}

Explain in 2-3 sentences why this symbol received this action bucket.
Be specific about the signal combination. No jargon beyond what's in the data."""
```

## Integration in scan.py

```python
if args.explain:
    from market_scanner.llm.explainer import explain_row
    for row in rows:
        row["explanation"] = explain_row(row)
```

## Rules

- Post-scan only — LLM never influences scanner decisions
- `--explain` is opt-in; without it, zero impact on existing behavior
- Failure (no key, timeout, API error) → empty string, run continues
- `anthropic` SDK is an optional dependency — import inside the function
- Target module: `market_scanner/llm/` — never `options_tech_scanner`
- Use `claude-haiku-4-5` by default — fast and cheap for this use case
