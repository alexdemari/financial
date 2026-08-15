# T18 — IBKR Flex Query integration: Cash Transactions

## Context

`financial` currently has no reliable source of deposit/withdrawal history. Portfolio
performance (TWR) is available via the IBKR Client Portal API, but reconciling actual
contributed capital (for MWR/XIRR, and for accurate "money in vs money out" reporting)
requires cash transaction data that only the Flex Web Service exposes.

A Flex Query has already been created in the IBKR Client Portal:
- Sections: `Cash Transactions` (types: Deposits/Withdrawals, Broker Interest, Broker Fees,
  Dividends), and `Change in NAV`.
- Delivery format: XML.
- A Flex Web Service token has been generated (expires ~1 year from creation).

This task implements the client that pulls this query and persists the results, so the
rest of the system (dashboard, dividend tracker, tax reporting) can use real cash-flow
data instead of estimates.

## Objective

Add a `financial/ibkr/flex_query.py` module that:
1. Executes the two-step IBKR Flex Web Service workflow (`SendRequest` → `GetStatement`)
   against the existing Flex Query.
2. Parses the returned XML into typed records.
3. Persists results to local storage (see Storage below).
4. Is callable via a `just` recipe and safe to run on a schedule (cron / CI) without
   hitting IBKR's rate limit.

## Requirements

### Config

- Read `IBKR_FLEX_TOKEN` and `IBKR_FLEX_QUERY_ID` from environment (`.env` via existing
  config loader pattern used elsewhere in the project — check `AGENTS.md` / existing
  `ibkr` module for the convention already in use, don't invent a new one).
- Fail fast with a clear error if either is missing — do not silently no-op.
- Document both variables in `.env.example` and in the relevant `docs/ai/skills/` or
  `docs/architecture/` page (whichever already documents IBKR credentials).

### Client (`flex_query.py`)

- `send_request() -> str`: calls `SendRequest`, returns `ReferenceCode`. Raise
  `FlexQueryError` on any `Status != "Success"` response, including the error code and
  message from IBKR in the exception text.
- `get_statement(reference_code: str) -> str`: calls `GetStatement`, polls on error code
  `1019` ("statement generation in progress") with exponential backoff (start ~5s, cap
  ~30s), up to a configurable max wait (default 2 minutes total). Raises `FlexQueryError`
  on any other error code or on timeout.
- `fetch_cash_transactions() -> list[CashTransaction]`: orchestrates the two calls above
  and parses `<CashTransaction>` elements from the response XML.
- `fetch_nav_changes() -> list[NavChange]`: same orchestration, parses the
  `<ChangeInNAV>` section (starting/ending NAV, deposits, withdrawals, PnL components for
  each period the query covers).
- Use `httpx` (already a project dependency — confirm in `pyproject.toml`, add if not
  present via `uv add httpx`).
- Respect IBKR's Flex Web Service rate limit (effectively ~1 request per query per 5
  minutes) — do not add retry logic that could hammer the endpoint; the module should
  assume it's invoked infrequently (scheduled), not from interactive/dashboard code paths.

### Data model

```python
@dataclass
class CashTransaction:
    date: str            # yyyymmdd
    type: str             # "Deposits/Withdrawals", "Broker Interest Paid", etc.
    amount: float
    currency: str
    description: str

@dataclass
class NavChange:
    from_date: str
    to_date: str
    starting_value: float
    ending_value: float
    deposits_withdrawals: float
    net_trades: float
    # include whatever other fields the actual XML exposes — inspect a real
    # response first rather than guessing the schema
```

Inspect a real `GetStatement` XML response before finalizing field names — the exact
attribute names in `<CashTransaction>` and `<ChangeInNAV>` should be confirmed against
actual output, not assumed from IBKR's generic docs.

### Storage

- Persist to whatever local storage `financial` already uses for structured data (check
  existing modules — likely SQLite given the project's local-first design; don't
  introduce a new storage engine).
- Table `cash_transactions`: one row per `CashTransaction`, deduplicated on
  `(date, type, amount, description)` so repeated runs are idempotent (upsert, not
  append-only).
- Table `nav_changes`: one row per period returned by the query, also idempotent.

### CLI / just recipe

- Add `just ibkr-flex-sync` that runs the fetch-and-persist flow end to end and prints a
  short summary (rows inserted/updated, date range covered).
- Should be safe to run manually and safe to run daily via cron/CI — running it twice in
  a row should not duplicate data or double-count deposits.

### Tests

- Unit tests with a fixture XML file (`tests/fixtures/flex_cash_transactions.xml`) for
  the happy path and for the `1019`/error-code paths — do not hit the real IBKR endpoint
  in tests.
- A reconciliation test: given `starting_value + deposits_withdrawals + net_trades ==
  ending_value` (within floating-point tolerance) for each `NavChange` row, assert it
  holds on the fixture data. Surface a warning (not a hard failure) if it doesn't hold on
  real data, since rounding/timing differences are expected.

### Out of scope for this task

- Wiring this into the dashboard or `tracker_builder.py` — that's a follow-up task once
  data is flowing and verified.
- Automatic token renewal — the token is long-lived (~1 year); just log a clear warning
  if IBKR returns an auth error suggesting expiry.
- Historical backfill beyond what the Flex Query's date range allows (IBKR Flex Queries
  typically cap lookback at ~1 year — confirm the actual configured range and note the
  limitation in the module docstring).

## Acceptance criteria

- [ ] `just ibkr-flex-sync` runs cleanly against the real Flex Query and populates
      `cash_transactions` / `nav_changes` in local storage.
- [ ] Re-running it does not create duplicate rows.
- [ ] Missing env vars produce a clear, actionable error (not a stack trace from deep
      inside `httpx`).
- [ ] Unit tests pass without network access.
- [ ] `.env.example` and the relevant docs page mention `IBKR_FLEX_TOKEN` and
      `IBKR_FLEX_QUERY_ID`.

## References

- Flex Query setup guide (already in project docs) — two-step HTTP workflow and the
  Flex Query configuration itself.
- IBKR Flex Web Service base URL:
  `https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService`
