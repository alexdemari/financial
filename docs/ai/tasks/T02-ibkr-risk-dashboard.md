# Task: IBKR Risk Dashboard — Cash Coverage, Concentration, Delta Proxy

**Status:** Completed
**Skill:** add-feature
**Scope:** `src/ibkr_positions/risk.py`, `src/ibkr_positions/html_report.py`, `src/ibkr_positions/report.py`
**Effort:** M
**Depends on:** T01 (live options export in place; positions model stable)

---

## Context

The current `ibkr_positions` report already computes basic risk metrics:
- `concentration_risk`: flags symbols above 25% of NLV
- `cash_coverage`: cash vs worst-case assignment cost of all short puts
- `margin_utilization`: initial_margin / NLV

However, two critical gaps exist:

**Gap 1 — Cash shortfall is flagged but not actionable.**
Current account has a $18,276.79 shortfall if all short puts are assigned
(worst-case cost $32,300 vs $14,023 cash). The report shows the number but
does not suggest how to resolve it (e.g., close SMR or PEP, add cash).

**Gap 2 — Delta proxy is not calculated.**
IBKR does not return Greeks in the portfolio endpoint without a market data
subscription. But approximate delta can be inferred from moneyness + DTE using
the Black-Scholes approximation or a simplified lookup. Without it, net
directional exposure of the options book is invisible.

**Gap 3 — Concentration limit is hardcoded at 25% with no per-symbol context.**
AAPL at 47.4% of NLV needs a named action, not just an alert.

---

## Goal

Extend `risk.py` with three new calculations and surface them in the HTML report
and markdown report as an "Enhanced Risk" section.

---

## Outcome spec

When done, the following must be true:

1. `risk.py` exports `cash_shortfall_resolution(portfolio)` returning a list of
   suggested actions to eliminate or reduce the cash shortfall (e.g., close
   highest-loss short put first).
2. `risk.py` exports `delta_proxy(position)` returning an approximate delta
   for any option position using Black-Scholes normal approximation (no external
   library needed — use `math.erf` or a hand-coded N(d1) for a single-call impl).
3. `risk.py` exports `portfolio_net_delta(portfolio)` returning the sum of
   `delta_proxy(p) × quantity × 100` across all option positions.
4. HTML report gains a "Enhanced Risk" section with:
   - Net portfolio delta (numerical + qualitative: bullish / bearish / neutral ±0.10)
   - Cash shortfall resolution suggestions (ranked by impact)
   - Concentration details per flagged symbol with suggested action
5. Markdown report mirrors the same section in text form.
6. `uv run pytest tests/ibkr_positions/test_risk.py` passes (≥8 tests).
7. No change to existing `concentration_risk`, `margin_utilization`, or
   `cash_coverage` function signatures.

---

## Constraints

- No external options pricing library (no `mibian`, no `py_vollib`).
  Use standard library `math` only for the delta approximation.
- Assume implied volatility = 30% as a fixed default (configurable constant,
  not a CLI flag). Document this clearly in the module docstring.
- Risk-free rate = 5.0% (Selic proxy). Same: configurable constant.
- Delta approximation is labeled "approximate" in all output — never presented
  as an exact Greek.
- No changes to `models.py` data structures — work with existing `Position` fields.

---

## Key design

### Delta proxy (simplified Black-Scholes d1)

```python
import math

IV_DEFAULT = 0.30   # implied volatility assumption
RF_DEFAULT = 0.05   # risk-free rate assumption (Selic proxy)

def delta_proxy(position: Position, *, iv: float = IV_DEFAULT, rf: float = RF_DEFAULT) -> float:
    """
    Approximate Black-Scholes delta for a single option leg.
    Uses fixed IV and RF — clearly labeled as an estimate.
    Returns delta in range [-1, 1].
    For short positions: caller multiplies by position.quantity (negative).
    """
    if not position.expiration or not position.strike:
        return 0.0

    T = (date.fromisoformat(position.expiration) - date.today()).days / 365
    if T <= 0:
        return 0.0

    S = position.market_value / (abs(position.quantity) * 100) or 1.0
    # use underlying price proxy from cost_basis / |qty| / 100 if available
    K = position.strike
    d1 = (math.log(S / K) + (rf + 0.5 * iv**2) * T) / (iv * math.sqrt(T))

    # N(d1) via error function
    nd1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))

    if position.option_type == "CALL":
        return nd1
    elif position.option_type == "PUT":
        return nd1 - 1
    return 0.0


def portfolio_net_delta(portfolio: Portfolio) -> float:
    """Sum of delta × quantity × 100 across all option positions."""
    total = 0.0
    for pos in portfolio.positions:
        if pos.asset_type == "OPT":
            d = delta_proxy(pos)
            total += d * pos.quantity * 100
    return total
```

### Cash shortfall resolution

```python
def cash_shortfall_resolution(portfolio: Portfolio) -> list[dict]:
    """
    Ranked list of actions to close the cash shortfall.
    Returns [] if no shortfall.
    """
    shortfall = max(0.0, portfolio.worst_case_assignment - portfolio.account.total_cash)
    if shortfall <= 0:
        return []

    # Sort short puts by highest unrealized loss (most costly to keep)
    short_puts = [p for p in portfolio.positions
                  if p.asset_type == "OPT" and p.option_type == "PUT" and p.quantity < 0]
    short_puts_sorted = sorted(short_puts, key=lambda p: p.unrealized_pnl)

    actions = []
    remaining = shortfall
    for p in short_puts_sorted:
        assignment_cost = abs(p.quantity) * p.strike * 100
        actions.append({
            "action": "CLOSE",
            "symbol": p.symbol,
            "assignment_cost": assignment_cost,
            "unrealized_pnl": p.unrealized_pnl,
            "shortfall_reduction": min(assignment_cost, remaining),
        })
        remaining -= assignment_cost
        if remaining <= 0:
            break

    return actions
```

Files to create/modify:
```
src/ibkr_positions/risk.py          ← add 3 new functions
src/ibkr_positions/html_report.py   ← add Enhanced Risk section
src/ibkr_positions/report.py        ← add Enhanced Risk section (markdown)
tests/ibkr_positions/test_risk.py   ← extend with 8+ new tests
```

---

## Tests (minimum 8)

```python
def test_delta_proxy_call_atm_is_near_0_5()
# ATM call (S≈K, T=30d) → delta ≈ 0.50 ± 0.05

def test_delta_proxy_put_atm_is_near_minus_0_5()
# ATM put → delta ≈ -0.50 ± 0.05

def test_delta_proxy_expired_option_returns_zero()
# T = 0 days → delta = 0.0

def test_delta_proxy_non_option_returns_zero()
# position.option_type = None → 0.0

def test_portfolio_net_delta_sums_all_legs()
# 2 short puts (delta -0.3 each, qty -1) + 1 short call (delta 0.1, qty -1)
# = (-0.3 × -1 × 100) × 2 + (0.1 × -1 × 100) = 60 - 10 = 50

def test_cash_shortfall_resolution_empty_when_no_shortfall()
# cash > worst_case_assignment → []

def test_cash_shortfall_resolution_ranks_by_loss()
# highest unrealized_pnl loss comes first in suggestions

def test_cash_shortfall_resolution_stops_when_shortfall_covered()
# if closing first put covers full shortfall, no further actions returned
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/ibkr_positions/test_risk.py -v

# 2. Generate a live report and inspect Enhanced Risk section
just ibkr-positions
open reports/output/ibkr_positions_$(date +%Y-%m-%d).html

# Expected:
# - Net portfolio delta displayed (bullish/bearish/neutral)
# - Cash shortfall resolution: SMR listed first (largest loss)
# - AAPL concentration suggestion present

# 3. Lint
uv run ruff check src/ibkr_positions/risk.py
```

---

## Known limitations / follow-up

- Delta proxy uses fixed IV=30% and RF=5%. Real accuracy requires market data
  subscription. This is intentional and clearly labeled in output.
- Underlying spot price for delta calculation is approximated from cost_basis
  divided by quantity. A dedicated underlying price lookup (T03) would improve accuracy.
- Theta and Vega are not calculated in this task.
