# Task: Dividend tracker calibration history

**Status:** Done
**Skill:** dividend-analysis
**Scope:** config/dividend_portfolio.yaml + docs/architecture/dividend-tracker.md

---

## Goal

Document the calibration decisions made for dividend_tracker asset configuration
so future sessions start with full context without re-analysis.

---

## Outcome spec

1. All asset calibration decisions are recorded with empirical evidence
2. Future Codex sessions can read this file instead of re-running diagnosis
3. Rationale for each ceiling_method and min_dy choice is explicit

---

## Calibration decisions (2026-06-11)

### EGIE3 → replaced by TAEE11

Reason: EGIE3 structural DY of 3.4–4.3% never reached 6% historically.
TAEE11 (pure transmission, ANEEL contract) delivers 7.7–8.4% DY with equal
or lower risk.

Data points used:
- EGIE3 TTM (yfinance): R$1.21, DY 3.56% at R$33.86
- TAEE11 TTM (yfinance): R$3.28, DY 8.41% at R$38.94
- TAEE11 avg_6y (2020–2025, excl. 2026): R$3.56, ceiling at 6% = R$59.35

Decision: replace EGIE3 with TAEE11, weight 0.25, ceiling_method: average_6y,
min_dy: 0.06

---

### ITSA4 — changed ceiling_method from average_6y to trailing

Reason: Itaúsa grew dividends 14× over 5 years (R$0.12 in 2020 → R$1.72 in
2025). The six-year average (R$0.57) drastically understates current capacity.

Data points used (yfinance, 2026-06-11):
- TTM: R$1.23 → DY 9.81% at R$12.53 → ceiling R$20.48 → BUY
- avg_6y: R$0.57 → ceiling R$9.45 → OVERPRICED (incorrect)

Decision: ceiling_method: trailing, min_dy: 0.06

---

### BBSE3 — no change

Reason: BB Seguridade is the only BR asset where 6% min_dy is correct.
Historical DY consistently 6–12%. avg_6y adequate (no growth distortion).

Data points: TTM R$4.55 (DY 12.1%), avg_6y R$2.41, both methods → BUY

Decision: ceiling_method: average_6y, min_dy: 0.06 (keep)

---

### VIVT3 — changed ceiling_method from average_6y to trailing

Reason: avg_6y penalises recent dividend growth (R$0.98 in 2020 → R$1.72
in 2025). TTM R$2.42 (DY 7.27%) already exceeds 6% criterion.

Data points:
- TTM: R$2.42 → ceiling R$40.33 → BUY at R$33.30
- avg_6y: R$1.43 → ceiling R$23.85 → OVERPRICED (incorrect)

Decision: ceiling_method: trailing, min_dy: 0.06

---

### SAPR4 — changed min_dy from 6% to 4.5%

Reason: Saneamento sector structural DY is 4–5%, not 6%. SAPR4 has never
reached 6% DY historically except in severe market stress.

Data points (excl. 2026 incomplete year):
- avg_6y (2020–2025): R$0.274 → ceiling at 4.5% = R$6.09
- Current price R$7.18 → OVERPRICED at correct min_dy

Decision: ceiling_method: average_6y, min_dy: 0.045
Note: SAPR4 correctly appears as OVERPRICED at current price (R$7.18 > R$6.09)

---

### USD ETFs (SCHD, DGRO, VYM) — min_dy set to historical average

Reason: USD ETFs have structural DY of 2.5–3.5%, never 6%. Using global
min_dy of 6% would permanently mark them as OVERPRICED.

min_dy set to each ETF's historical average DY:
- SCHD: 3.4%
- DGRO: 2.8%
- VYM: 3.0%

Interpretation: DY above the historical average = asset relatively cheap
vs its own history.

---

### PEP — monitored asset (target_weight: 0.0)

Reason: PEP is operated via recurring cash-secured put selling on IBKR,
not direct contribution. Appears in report for monitoring but excluded from
budget allocation.

min_dy: 3.8% (US Dividend King historical DY range 2.5–4.5%)
ceiling_method: trailing
Current position: short PUT $140 Jul'26, premium $2.86, delta 0.32

---

## avg_6y bug fix (2026-06-11)

`calculate_average_annual_dividend` was including the current incomplete year
in the six-year average, pulling it down systematically.

Fix: filter out `year == date.today().year` before computing the average.

Example impact on SAPR4:
- Before fix: avg includes 2026 (R$0.11 partial) → avg R$0.251
- After fix: avg 2020–2025 only → avg R$0.274

---

## Technical analysis removal (2026-06-11)

After 10-year backtests (1D and 1W) on all portfolio assets:
- lux 1D: 25–40% precision, 10–15 signals/year (noisy for monthly DCA)
- smc 1D: 37–57% precision, 0.4–0.8 signals/year (too infrequent)
- rsi-sma: 0 signals over 10 years

Decision: remove stock_analyzer dependency from dividend_tracker. Price ceiling
vs current price is the only criterion. AssetDecision simplified to BUY /
OVERPRICED (removed WATCH, WAIT, ConvictionLevel).

Backtest reports preserved in reports/backtest/ for reference.

---

## Known limitations / follow-up

- SAPR4 is structurally OVERPRICED at current price levels. Monitor for
  entry when price drops below R$6.09 (avg_6y / 4.5%)
- USD ETFs min_dy values are based on observed historical averages, not
  formal statistical analysis. Revisit annually.
- JCP (Juros sobre Capital Próprio) for Brazilian assets: yfinance includes
  JCP in the dividends series for BR tickers — confirmed for ITSA4 (8 events
  in TTM). No separate adjustment needed.
