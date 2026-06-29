# ibkr_trades

## Purpose

Maintains a canonical, append-only trade execution history sourced from IBKR
and derives `options_tracker.csv` automatically — eliminating manual CSV
maintenance.

This module is read-only with respect to IBKR: it never submits or modifies
orders.

---

## Data Flow

```
IBKR Flex Query XML (one-time backfill)
IBKR Client Portal API via ib_insync (daily incremental sync)
        ↓
data/ibkr/trades_history.csv   ← canonical store (append-only, gitignored)
        ↓
options_tracker.csv            ← derived: open option legs only
        ↓
exit_monitor / daily_report    ← unchanged consumers
```

---

## Usage

```bash
# One-time backfill from Flex Query XML export
# Export from IBKR: Reports → Activity → Flex Queries → All trades since inception → XML
just ibkr-backfill flex=data/ibkr/flex_export.xml

# Rebuild options_tracker.csv from history (offline, no Gateway needed)
just ibkr-generate-tracker

# Daily flow: sync new trades + rebuild tracker
just ibkr-trades-daily

# ibkr-positions runs sync + generate-tracker automatically before the report
just ibkr-positions
```

---

## Module Structure

```
src/ibkr_trades/
├── models.py           — TradeRecord dataclass (canonical schema)
├── flex_parser.py      — Flex Query XML → list[TradeRecord]
├── api_fetcher.py      — ib_insync reqExecutions → list[TradeRecord] (incremental)
├── store.py            — trades_history.csv read/write/dedup/append
├── roll_detector.py    — same-day close+open pair detection, assigns shared roll_id
├── strategy_tagger.py  — infers strategy from trade fields (csp, covered_call, etc.)
├── tracker_builder.py  — derives options_tracker.csv from open legs in history
└── main.py             — CLI: backfill | sync | generate-tracker | full
```

---

## Canonical Trade Record Schema (`trades_history.csv`)

| Column | Type | Notes |
|---|---|---|
| `trade_id` | str | IBKR execId / Flex TradeID — deduplication key |
| `date` | date | YYYY-MM-DD trade date |
| `datetime` | str | ISO datetime of execution |
| `symbol` | str | IBKR local symbol |
| `underlying` | str | Underlying ticker |
| `asset_type` | str | `STK` \| `OPT` \| `ETF` |
| `option_type` | str\|None | `CALL` \| `PUT` \| None |
| `strike` | float\|None | Options only |
| `expiration` | str\|None | YYYY-MM-DD |
| `quantity` | float | positive=buy, negative=sell |
| `price` | float | Execution price per unit |
| `proceeds` | float | qty × price × multiplier |
| `commission` | float | Negative |
| `pnl_realized` | float\|None | Populated by Flex XML; null for API-sourced rows |
| `currency` | str | USD |
| `open_close` | str | `O` \| `C` \| `O;C` |
| `source` | str | `flex` \| `api` |
| `roll_id` | str\|None | UUID shared by roll pair |
| `strategy` | str\|None | `covered_call` \| `csp` \| `long_call` \| `long_put` \| `roll` \| `other` |

---

## `options_tracker.csv` Generation

`tracker_builder.py` computes net open quantity per contract by summing
`quantity` across all trades for that contract key
(`underlying`, `option_type`, `strike`, `expiration`).
Contracts with `|net_qty| > 0.001` are written as open legs.

Output uses the existing semicolon-delimited schema consumed by
`market_scanner.portfolio.load_open_positions`. Three additive columns
(`trade_id`, `roll_id`, `strategy`) are appended after the canonical 26 —
`exit_monitor` ignores unknown columns.

Any pre-existing manually maintained `options_tracker.csv` is archived to
`data/ibkr/options_tracker_manual_backup_YYYY-MM-DD.csv` on the first run.

---

## Roll Detection

A roll is two trades on the same date for the same underlying and option type
where one is a closing trade (`open_close` contains `C`) and the other is an
opening trade (`open_close == O`) on a **different expiration**. Both rows are
assigned a shared `roll_id` UUID.

---

## Deduplication

`trade_id` is the deduplication key. Two rows with the same `trade_id` in a
single batch or across multiple runs result in exactly one stored row (the
first occurrence).

---

## Append-Only Contract

Rows in `trades_history.csv` are never deleted or modified after being written.
The sole permitted post-write mutation is filling null `roll_id` and `strategy`
fields, which `_tag_history()` performs in `main.py` immediately after each
append.

---

## Known Limitations

- `pnl_realized` is not populated by the incremental API sync (`reqExecutions`
  does not return P&L). Populated by Flex XML only.
- `open_close` from `reqExecutions` may be absent in older API responses;
  the tracker builder infers open/closed state from net quantity, which is
  more robust than trusting `openCloseIndicator` from the API.
- Roll detection uses same-day heuristic only. Same-week rolls are not detected.
- Strategy tagger cannot distinguish cash-secured from naked puts — it does not
  verify cash coverage (that check lives in `ibkr_positions.risk`).

---

## Connection

`ibkr-sync` uses `ib_insync` with `readonly=True`, `timeout=10s`,
`client_id=11` (different from `ibkr_positions` which uses `client_id=10`
to avoid TWS client ID conflicts).
