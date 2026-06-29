# Task T10: Programmatic Flex Query Download (`flex_fetcher.py`)

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/ibkr_trades/flex_fetcher.py` (new), `justfile`
**Effort:** S
**Depends on:** T09 (ibkr_trades module and .env pattern established)

---

## Context

T09 implemented `ibkr-backfill` to parse a Flex Query XML and populate
`trades_history.csv`. However, the XML file itself must currently be downloaded
manually from the IBKR Client Portal every time. This means:

- `pnl_realized` is only ever populated at backfill time (initial run).
- Any trades executed after the last manual download lack P&L data.
- The daily flow (`just ibkr-trades-daily`) cannot be fully automated without
  someone logging into the portal.

The IBKR **Flex Web Service** API allows programmatic retrieval of any saved
Flex Query report using a token and query ID — both of which are now configured
(token and query ID captured during Flex Query setup).

This task adds `flex_fetcher.py` to `ibkr_trades`, wires it into
`ibkr-trades-daily`, and ensures `pnl_realized` is always populated in the
canonical history store.

---

## Goal

Implement `ibkr_trades.flex_fetcher` — a module that downloads the latest
Flex Query XML from IBKR via the Flex Web Service API using credentials from
`.env`, saves it to disk, and returns the path for consumption by
`flex_parser.py`.

Wire the fetcher into `ibkr-trades-daily` so the full flow —
fetch → backfill → generate-tracker — runs without any manual step.

---

## Outcome spec

When done, the following must be true:

1. `just ibkr-flex-fetch` downloads the Flex Query XML to
   `data/ibkr/flex_latest.xml` using `IBKR_FLEX_TOKEN` and
   `IBKR_FLEX_QUERY_ID` from `.env`. No browser, no portal login.
2. `just ibkr-trades-daily` calls `ibkr-flex-fetch` before `ibkr-backfill`,
   so the history always reflects the latest Flex data including `pnl_realized`.
3. `flex_fetcher.py` implements the two-step Flex Web Service workflow:
   - Step A: `GET /SendRequest?t={token}&q={query_id}&v=3` → `ReferenceCode`
   - Step B: `GET /GetStatement?t={token}&q={ref_code}&v=3` → XML bytes
4. Retries Step B up to 5 times with 5-second waits (IBKR generation delay).
5. On `ErrorCode 1003` (statement not available — data not yet refreshed for
   the day), prints a clear human-readable warning and exits 0 gracefully
   rather than crashing — the prior `flex_latest.xml` remains valid.
6. On token expiry (`ErrorCode 1012`), prints actionable message:
   `"Flex token expired. Renew at: Settings → Account Settings → Flex Web Service"`
7. All HTTP calls use `urllib.request` (stdlib only — no new dependencies).
8. `uv run pytest tests/ibkr_trades/test_flex_fetcher.py` passes (≥ 6 tests).
9. `.env.example` exists at project root with all required variables documented.

---

## Constraints

- No new pip dependencies. `urllib.request` + stdlib only.
- No async.
- The fetcher never parses the XML — it only downloads and saves bytes.
  Parsing is `flex_parser.py`'s responsibility (separation of concerns).
- If `IBKR_FLEX_TOKEN` or `IBKR_FLEX_QUERY_ID` are missing from env,
  raise `EnvironmentError` with a clear message before making any HTTP call.
- Downloaded XML is written atomically: write to `flex_latest.xml.tmp`,
  then rename to `flex_latest.xml`. Avoids corrupt partial downloads.
- All HTTP requests include `User-Agent: financial/1.0` header
  (required by IBKR Flex Web Service).

---

## Key design

```python
# src/ibkr_trades/flex_fetcher.py

import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SEND_URL = (
    "https://gdcdyn.interactivebrokers.com"
    "/Universal/servlet/FlexStatementService.SendRequest"
    "?t={token}&q={query_id}&v=3"
)

HEADERS = {"User-Agent": "financial/1.0"}

# Error codes from IBKR Flex Web Service
_RECOVERABLE_CODES = {"1001", "1004", "1019"}   # retry
_DATA_NOT_READY    = {"1003", "1005", "1006"}    # skip gracefully
_TOKEN_ERRORS      = {"1012", "1013", "1015"}    # actionable message


def fetch_flex_query(
    output_path: Path,
    *,
    max_retries: int = 5,
    retry_wait: float = 5.0,
) -> Path | None:
    """
    Downloads the latest Flex Query XML from IBKR Flex Web Service.
    Reads IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID from environment.

    Returns output_path on success.
    Returns None if data is not yet available for the day (error 1003/1005/1006).
    Raises RuntimeError for unrecoverable errors.
    Raises EnvironmentError if credentials are missing.
    """
    token    = _require_env("IBKR_FLEX_TOKEN")
    query_id = _require_env("IBKR_FLEX_QUERY_ID")

    # Step A — request report generation
    send_url = SEND_URL.format(token=token, query_id=query_id)
    response_xml = _get(send_url)
    root = ET.fromstring(response_xml)

    status = root.findtext("Status")
    if status != "Success":
        error_code = root.findtext("ErrorCode", "")
        error_msg  = root.findtext("ErrorMessage", "unknown error")
        return _handle_error(error_code, error_msg)

    ref_code = root.findtext("ReferenceCode")
    base_url = root.findtext("Url")
    get_url  = f"{base_url}?t={token}&q={ref_code}&v=3"

    # Step B — retrieve generated report (with retries)
    for attempt in range(max_retries):
        time.sleep(retry_wait)
        content = _get(get_url)

        # Check if still pending or error
        if b"<Status>" in content:
            err_root  = ET.fromstring(content)
            err_code  = err_root.findtext("ErrorCode", "")
            err_msg   = err_root.findtext("ErrorMessage", "unknown")
            if err_code in _RECOVERABLE_CODES and attempt < max_retries - 1:
                print(f"  Flex: report not ready (attempt {attempt+1}/{max_retries}), retrying...")
                continue
            return _handle_error(err_code, err_msg)

        # Success — write atomically
        tmp = output_path.with_suffix(".xml.tmp")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(content)
        tmp.rename(output_path)
        print(f"✓ Flex Query downloaded: {output_path} ({len(content):,} bytes)")
        return output_path

    raise RuntimeError("Flex GetStatement: report not ready after all retries")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Add it to .env — see .env.example for reference."
        )
    return val


def _handle_error(code: str, msg: str) -> None:
    if code in _DATA_NOT_READY:
        print(
            f"⚠ Flex data not yet available for today (error {code}: {msg}).\n"
            f"  Activity statements update after market close (~22:00 ET).\n"
            f"  Using existing flex_latest.xml if present."
        )
        return None
    if code in _TOKEN_ERRORS:
        raise RuntimeError(
            f"Flex token error ({code}: {msg}).\n"
            f"Renew at: Client Portal → Settings → Account Settings → Flex Web Service"
        )
    raise RuntimeError(f"Flex Web Service error {code}: {msg}")


# CLI entry point
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path("data/ibkr/flex_latest.xml"))
    args = parser.parse_args()
    result = fetch_flex_query(args.output)
    if result is None:
        print("Skipped — using existing file.")
```

---

## Justfile changes

### Add `ibkr-flex-fetch` recipe

```just
# Download latest Flex Query XML from IBKR (requires IBKR_FLEX_TOKEN in .env).
# Skips gracefully if IBKR data not yet refreshed for today.
ibkr-flex-fetch output="data/ibkr/flex_latest.xml":
    PYTHONPATH=src uv run python -m ibkr_trades.flex_fetcher \
        --output {{output}}
```

### Update `ibkr-trades-daily` to call fetch before backfill

```just
# Full daily flow: fetch latest Flex XML → sync new trades → rebuild options_tracker.csv.
ibkr-trades-daily host="" port="7496":
    just ibkr-flex-fetch                                        # ← NEW: download latest XML
    just ibkr-backfill flex=data/ibkr/flex_latest.xml          # ← backfill (idempotent)
    just ibkr-sync host={{host}} port={{port}}                  # ← API incremental sync
    just ibkr-generate-tracker
    @echo "✓ options_tracker.csv rebuilt from live trade history"
```

The backfill step is idempotent (deduplicates by `trade_id`), so running it
daily with an updated XML is safe and fills in `pnl_realized` for recently
closed positions.

---

## `.env.example` (create at project root)

```bash
# ── IBKR Connection (IB Gateway / TWS) ───────────────────────────────────────
# IB Gateway must be running on Windows; WSL2 connects via the default route IP.
# Leave blank — ibkr-* recipes auto-detect WSL2 host IP via `ip route show default`.
IBKR_HOST=
IBKR_PORT=7496

# ── IBKR Flex Web Service ────────────────────────────────────────────────────
# Required for: just ibkr-flex-fetch, just ibkr-trades-daily
# Setup: Client Portal → Settings → Account Settings → Flex Web Service
IBKR_FLEX_TOKEN=
# Setup: Client Portal → Performance & Reports → Flex Queries → ℹ️ icon → Query ID
IBKR_FLEX_QUERY_ID=

# ── LLM Providers ────────────────────────────────────────────────────────────
# Required for: just daily-report-llm
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

Files to create/modify:
```
src/ibkr_trades/flex_fetcher.py          ← NEW
tests/ibkr_trades/test_flex_fetcher.py   ← NEW
.env.example                             ← NEW
justfile                                 ← add ibkr-flex-fetch; update ibkr-trades-daily
```

---

## Tests (minimum 6)

```python
def test_fetch_success_writes_file(tmp_path, monkeypatch)
# Mock both HTTP calls to return valid XML → output file written with correct bytes

def test_fetch_retries_on_recoverable_error(tmp_path, monkeypatch)
# Step B returns error 1019 twice then succeeds → file written after 3 attempts

def test_fetch_returns_none_on_data_not_ready(tmp_path, monkeypatch)
# Step A returns error 1003 → returns None, no exception, prints warning

def test_fetch_raises_on_token_expiry(tmp_path, monkeypatch)
# Step A returns error 1012 → raises RuntimeError with renewal instructions

def test_fetch_raises_on_missing_token(tmp_path, monkeypatch)
# IBKR_FLEX_TOKEN not in env → raises EnvironmentError before any HTTP call

def test_fetch_writes_atomically(tmp_path, monkeypatch)
# Confirm .xml.tmp is renamed to .xml (no partial file left on success)
```

---

## Verification

```bash
# 1. Tests (no network — all HTTP mocked)
uv run pytest tests/ibkr_trades/test_flex_fetcher.py -v

# 2. Live fetch (requires IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID in .env)
just ibkr-flex-fetch
# Expected: ✓ Flex Query downloaded: data/ibkr/flex_latest.xml (N bytes)
ls -lh data/ibkr/flex_latest.xml

# 3. Full automated daily flow
just ibkr-trades-daily
# Expected:
# ✓ Flex Query downloaded
# Backfill complete.
# options_tracker.csv rebuilt from live trade history

# 4. Verify pnl_realized now populated for closed trades
grep -v "^trade_id" data/ibkr/trades_history.csv | \
  awk -F',' '$14 != "" && $14 != "0.0" {count++} END {print count, "rows with pnl_realized"}'

# 5. Graceful skip when data not ready (run before 22:00 ET)
# Expected: ⚠ Flex data not yet available... Using existing flex_latest.xml.

# 6. Lint
uv run ruff check src/ibkr_trades/flex_fetcher.py \
  tests/ibkr_trades/test_flex_fetcher.py
```

---

## Known limitations / follow-up

- Flex Activity data updates once per day after market close (~22:00 ET).
  Running before that returns error 1003 — the fetcher handles this gracefully
  but `pnl_realized` for trades executed today won't be available until the
  next day's Flex report.
- Token lifespan is set at creation time (up to 1 year). The fetcher does not
  auto-renew tokens — a `RuntimeError` with renewal instructions is raised when
  the token expires.
- Rate limit: IBKR enforces 10 requests/minute per token. The fetcher makes
  exactly 2 calls (SendRequest + GetStatement), well within limits.
