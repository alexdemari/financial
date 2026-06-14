# Skill: Dividend Portfolio Analysis

## When to use this skill

Use when:
- calibrating min_dy or ceiling_method for a new or existing asset
- diagnosing why an asset is showing OVERPRICED unexpectedly
- adding a new asset to dividend_portfolio.yaml
- reviewing dividend data quality from yfinance

---

## Step 1 — Extract real dividend data

Always verify with real yfinance data before changing any config.

```python
import yfinance as yf
import pandas as pd

ticker_str = 'TICKER.SA'   # add .SA for BR assets
ticker = yf.Ticker(ticker_str)
divs = ticker.dividends
price = ticker.fast_info.last_price

# TTM (fix timezone before comparing)
cutoff_ttm = pd.Timestamp.now(tz='America/Sao_Paulo') - pd.DateOffset(months=12)
ttm = divs[divs.index > cutoff_ttm]
ttm_total = ttm.sum()
dy_ttm = ttm_total / price * 100

# avg_6y — ALWAYS exclude current year
current_year = pd.Timestamp.now().year
cutoff_6y = pd.Timestamp.now(tz='America/Sao_Paulo') - pd.DateOffset(years=6)
hist = divs[divs.index > cutoff_6y].copy()
hist.index = hist.index.tz_convert('America/Sao_Paulo')
hist_complete = hist[hist.index.year < current_year]
by_year = hist_complete.groupby(hist_complete.index.year).sum()
avg6y = by_year.mean()

print(f'Price: {price:.2f}')
print(f'Events TTM: {len(ttm)}')
print(f'TTM total: {ttm_total:.4f}')
print(f'DY TTM: {dy_ttm:.2f}%')
print(f'Years in avg_6y: {len(by_year)} | {by_year.to_dict()}')
print(f'avg_6y: {avg6y:.4f}')
print(f'Ceiling TTM/6%: {ttm_total/0.06:.2f}')
print(f'Ceiling 6y/6%: {avg6y/0.06:.2f}')
```

---

## Step 2 — Choose ceiling_method

Use `trailing` when:
- The company has grown dividends rapidly (>50% over 5 years) — avg_6y
  would understate current capacity
- ETF with relatively linear dividend growth

Use `average_6y` when:
- Dividends are irregular year-to-year (typical for BR assets with JCP,
  extraordinary dividends)
- Growth is moderate and the historical average is representative

Red flag: if avg_6y ceiling is BELOW current price but TTM ceiling is
ABOVE it, the asset is a `trailing` candidate.

---

## Step 3 — Choose min_dy

Rule: min_dy should reflect the asset's structural (historical average) DY,
not an aspirational target.

Reference values (2026):
- BR regulated sectors (energy transmission, sanitation): 4–6%
- BR financials / insurance: 6–10%
- US Dividend Kings (PEP, KMB): 2.5–4.5%
- US broad dividend ETFs (SCHD, VYM, DGRO): 2.8–3.4%

If a 6% global min_dy would permanently mark an asset as OVERPRICED
(i.e. it has never reached 6% DY historically), reduce min_dy to match
the structural range.

---

## Step 4 — Validate the decision

After changing ceiling_method or min_dy, run:

```bash
just dividends-local budget=8000
```

Check:
- Does the decision (BUY / OVERPRICED) match your expectation?
- Is the price ceiling plausible given current price?
- Is the margin to ceiling reasonable (not 0% or 200%)?

---

## BR assets — JCP note

Brazilian assets pay both dividends and JCP (Juros sobre Capital Próprio).
yfinance includes both in the `ticker.dividends` series for `.SA` tickers.
No separate adjustment is needed. Verify by counting events:
- ITSA4 typically has 8–12 events per year (quarterly JCP + semiannual dividends)
- BBSE3 typically has 2–4 events per year
- TAEE11 typically has 4 events per year

If event count is unusually low (1–2 per year for assets expected to pay
quarterly), the dividend cache may be stale. Delete `data/dividends/<ticker>.json`
and re-run.

---

## avg_6y: never include the current year

The current year is incomplete. Including it pulls the average down.
`calculate_average_annual_dividend` enforces this — verify it is working
by checking the `by_year` dict: it should not contain the current year.

---

## Asset substitution criteria

Consider replacing an asset when:
1. Its structural DY is below the calibrated min_dy AND no plausible min_dy
   adjustment brings it into range
2. An alternative exists in the same sector with materially higher DY and
   equal or lower risk
3. The alternative has at least 5 years of complete dividend history

Example: EGIE3 (structural DY 3.4%) replaced by TAEE11 (structural DY 7.7%)
in the same energy sector.

Document the substitution in `docs/ai/tasks/dividend-tracker-calibration.md`.
