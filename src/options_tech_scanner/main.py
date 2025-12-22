# src/options_tech_scanner/main.py

import os
import argparse
import pandas as pd

from options_tech_scanner.context import compute_context
from options_tech_scanner.indicators import atr, rsi, sma
from options_tech_scanner.setups import classify_put_strategy
from options_tech_scanner.backtest import run_backtest_mode


# =========================
# SCAN DE CONTEXTO + TIMING
# =========================

def scan_directory(data_dir: str, mode: str = "core", verbose: bool = False) -> None:
    results = []
    near_results = []
    stage_universe = []
    stage_context = []
    stage_regime = []
    stage_timing = []
    stage_strategy = []


    for file in os.listdir(data_dir):
        if not file.lower().endswith(".csv"):
            continue

        symbol = file.replace(".csv", "").upper()
        path = os.path.join(data_dir, file)

        df = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")

        if len(df) < 300:
            continue

        stage_universe.append(symbol)
        
        # =========================
        # CONTEXT SCANNER
        # =========================
        context = compute_context(df)
        
        # Filtros estruturais mínimos
        if context["hv30"] is not None and context["hv30"] < 30:
            continue

        if context["trend_sma200_pct"] is not None and context["trend_sma200_pct"] < 0:
            continue

        if context["fvg"] and context["fvg"]["type"] == "BEARISH":
            continue

        stage_context.append(symbol)
        
        # =========================
        # TIMING SCANNER
        # =========================
        close = df["Close"]
        low = df["Low"]

        atr_series = atr(df)
        rsi_series = rsi(close)
        support_series = low.rolling(60).min()

        sma200 = sma(close, 200)
        bullish = (close.iloc[-1] > sma200.iloc[-1]) and (sma200.diff(20).iloc[-1] > 0)

        if not bullish:
            continue
        
        stage_regime.append(symbol)

        atr_val = atr_series.iloc[-1]
        support = support_series.iloc[-1]

        # reforço com Order Block
        if context["order_block"] is not None:
            support = max(support, context["order_block"])

        if atr_val == 0 or pd.isna(atr_val) or pd.isna(support):
            continue

        stage_timing.append(symbol)
        
        dist_atr = (close.iloc[-1] - support) / atr_val
        rsi_val = rsi_series.iloc[-1]

        strategy = classify_put_strategy(
            bullish=bullish,
            rsi_val=rsi_val,
            dist_atr=dist_atr,
            vol_ratio=1.0,  # proxy simples no scan
            mode=mode
        )

        if strategy:
            stage_strategy.append(symbol)
            results.append({
                "symbol": symbol,
                "strategy": strategy,
                "rsi": round(rsi_val, 2),
                "dist_atr": round(dist_atr, 2),
                "hv30": round(context["hv30"], 2)
            })
        else:
            if bullish and dist_atr < 0.8:
                near_results.append({
                    "symbol": symbol,
                    "rsi": round(rsi_val, 2),
                    "dist_atr": round(dist_atr, 2),
                    "hv30": round(context["hv30"], 2)
                })

    if verbose:
        print("\n🔍 ETAPAS DO SCAN:")
        print(f"Universo inicial: {len(stage_universe)} ativos")
        print(f"Após contexto:    {len(stage_context)}")
        print(f"Após regime:      {len(stage_regime)}")
        print(f"Após timing:      {len(stage_timing)}")
        print(f"Setups finais:    {len(stage_strategy)}")

        print("\n📌 Ativos por etapa:")
        print("Contexto OK:", stage_context[:20])
        print("Regime OK:", stage_regime[:20])
        print("Timing OK:", stage_timing[:20])

def compute_final_score(row):
    """
    Score final de priorização (0–100).
    """
    # --- distância ao suporte ---
    max_dist = 3.5
    dist_score = max(0, 1 - (row["dist_atr"] / max_dist))

    # --- RSI (centro ideal ~50) ---
    rsi_score = 1 - abs(row["rsi"] - 50) / 20
    rsi_score = max(0, min(rsi_score, 1))

    # --- volatilidade (cap em 80%) ---
    hv_score = min(row["hv30"] / 80, 1)

    # --- bônus por estratégia ---
    strat_bonus = 0.1 if row["strategy"] == "BULL_PUT_SPREAD" else 0.0

    score = (
        0.4 * dist_score +
        0.3 * rsi_score +
        0.3 * hv_score +
        strat_bonus
    )

    return round(score * 100, 2)


# =========================
# MAIN CLI
# =========================

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Options Tech Scanner")

    parser.add_argument("--data-dir", type=str, required=True, help="Diretório dos CSVs")
    parser.add_argument("--scan", action="store_true", help="Executar scan diário")
    parser.add_argument("--backtest", action="store_true", help="Executar backtest")
    parser.add_argument("--mode", choices=["core", "relaxed"], default="core")
    parser.add_argument("--lookahead", type=int, default=30)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Imprime ativos por etapa do filtro"
    )

    args = parser.parse_args()

    if args.scan:
        print(f"\n🔍 SCAN ({args.mode.upper()})")
        scan_directory(args.data_dir, mode=args.mode, verbose=args.verbose)

    if args.backtest:
        print(f"\n📈 BACKTEST ({args.mode.upper()})")
        events = run_backtest_mode(
            data_dir=args.data_dir,
            lookahead=args.lookahead,
            mode=args.mode
        )

        from options_tech_scanner.metrics import summary_by_strategy

        summary = summary_by_strategy(events)

        for strat, stats in summary.items():
            print(
                f"{strat}: "
                f"{stats['trades']} trades | "
                f"Win Rate = {stats['win_rate']:.2%}"
            )
