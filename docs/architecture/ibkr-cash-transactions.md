# ibkr_cash

## Purpose

Pulls deposit/withdrawal, dividend, interest, and fee history plus
period-over-period NAV reconciliation from a dedicated IBKR Flex Query, so
downstream tools (MWR/XIRR, "money in vs money out" reporting) can use real
cash-flow data instead of estimates.

Read-only with respect to IBKR: never submits or modifies orders.

---

## Data Flow

```
IBKR Flex Query XML (Cash Transactions + Change in NAV sections)
        ↓
data/ibkr/cash_transactions.csv   ← upserted, gitignored
data/ibkr/nav_changes.csv         ← upserted, gitignored
```

Both CSVs are upserted (not append-only): re-running `sync` on the same
period replaces that period's row rather than duplicating it, so the flow is
safe to run daily via cron/CI.

`cash_transactions` dedup key: `(date, type, amount, description)`.
`nav_changes` dedup key: `(from_date, to_date)`.

---

## Config

Requires a **separate** Flex Query from the one used by `ibkr_trades`
(different sections: Cash Transactions, Change in NAV; delivery format XML).
Set up in Client Portal → Performance & Reports → Flex Queries.

- `IBKR_FLEX_TOKEN` — shared with `ibkr_trades`.
- `IBKR_FLEX_QUERY_ID_CASH` — this query's id, distinct from
  `IBKR_FLEX_QUERY_ID`.

See `.env.example`. Missing either variable fails fast with a clear message
(`EnvironmentError`), not a stack trace from inside the HTTP client.

`net_trades` on `NavChange` is a derived catch-all — `ending_value -
starting_value - deposits_withdrawals` — rather than a field IBKR exposes
directly, so `starting_value + deposits_withdrawals + net_trades ==
ending_value` holds by construction for every row.

IBKR Flex Queries typically cap lookback at ~1 year; this module does not
backfill beyond whatever the configured query's date range covers.

---

## Usage

```bash
# Fetch the latest Cash Transactions Flex Query XML
just ibkr-cash-fetch

# Fetch + parse + upsert into local CSV stores in one step
just ibkr-flex-sync
```

Respects IBKR's Flex Web Service rate limit (~1 request per query per 5
minutes) — invoke on a schedule (daily cron), not from interactive/dashboard
code paths.

---

## Out of scope

- Wiring into the dashboard or `tracker_builder.py` (follow-up task once data
  is flowing and verified).
- Automatic token renewal — the token is long-lived (~1 year); an auth error
  from IBKR is logged as a clear expiry warning by the shared
  `ibkr_trades.flex_fetcher` error handling.
