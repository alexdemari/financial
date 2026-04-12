# src/options_tech_scanner/main.py

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from options_tech_scanner.backtest import run_backtest_mode
from options_tech_scanner.cache_utils import (
    load_indicator_cache,
    load_scan_result_cache,
    save_indicator_cache,
    save_scan_result_cache,
)
from options_tech_scanner.context import compute_context
from options_tech_scanner.indicators import avg_dollar_volume, compute_indicator_frame
from options_tech_scanner.setups import evaluate_put_setup


# =========================
# SCAN DE CONTEXTO + TIMING
# =========================


def _load_benchmark_df(data_dir: str, symbol: str) -> pd.DataFrame | None:
    path = os.path.join(data_dir, f"{symbol}.csv")
    if not os.path.exists(path):
        return None

    try:
        return _read_symbol_df(path)
    except Exception:
        return None


def _read_symbol_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], utc=True, errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date")
    return df.sort_index()


def compute_final_score(row: pd.Series) -> float:
    """
    Score final de priorizacao (0-100).
    """
    dist = row.get("dist_ema21_atr", float("nan"))
    if pd.isna(dist):
        dist_score = 0.0
    else:
        dist_score = max(0.0, 1 - (dist / 2.0))

    rsi_val = row.get("rsi", float("nan"))
    if pd.isna(rsi_val):
        rsi_score = 0.0
    else:
        rsi_score = 1 - abs(rsi_val - 45) / 25
        rsi_score = max(0.0, min(rsi_score, 1.0))

    vol_ratio = row.get("vol_ratio", float("nan"))
    if pd.isna(vol_ratio):
        vol_score = 0.0
    else:
        vol_score = min(vol_ratio / 2.0, 1.0)

    alpha_bonus = 0.10 if row.get("alpha_rotation", False) else 0.0
    pa_bonus = 0.08 if row.get("price_action_ok", False) else 0.0
    strat_bonus = 0.10 if row.get("strategy") == "BULL_PUT_SPREAD" else 0.0

    score = 0.35 * dist_score + 0.30 * rsi_score + 0.25 * vol_score
    score += alpha_bonus + pa_bonus + strat_bonus

    return round(max(0.0, min(score * 100, 100.0)), 2)


def _rsi_info_tags(rsi_value: float | None) -> tuple[str, str, str]:
    time_bias = "BUY_OPT:90-720D | SELL_OPT:7-42D"
    if rsi_value is None or pd.isna(rsi_value):
        return "UNKNOWN", "NONE", time_bias

    if rsi_value > 80:
        return (
            "OVERBOUGHT_80+",
            "MEAN_REV_SHORT_BIAS (buy_put/sell_call)",
            time_bias,
        )
    if rsi_value < 30:
        return (
            "OVERSOLD_30-",
            "MEAN_REV_LONG_BIAS (buy_call/sell_put)",
            time_bias,
        )
    return "NEUTRAL", "NONE", time_bias


def _bx_regime_from_close(close: pd.Series, min_periods: int = 60) -> str:
    if close is None or close.empty or len(close) < min_periods:
        return "UNKNOWN"

    ema8 = close.ewm(span=8, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    slope21 = ema21.diff()

    if pd.isna(ema8.iloc[-1]) or pd.isna(ema21.iloc[-1]) or pd.isna(slope21.iloc[-1]):
        return "UNKNOWN"

    if ema8.iloc[-1] > ema21.iloc[-1] and slope21.iloc[-1] > 0:
        return "BULLISH"
    if ema8.iloc[-1] < ema21.iloc[-1] and slope21.iloc[-1] < 0:
        return "BEARISH"
    return "NEUTRAL"


def _multi_timeframe_bx(df: pd.DataFrame) -> dict:
    close = df["Close"].dropna()
    weekly_close = close.resample("W-FRI").last().dropna()
    monthly_close = close.resample("ME").last().dropna()

    daily_bx = _bx_regime_from_close(close, min_periods=120)
    weekly_bx = _bx_regime_from_close(weekly_close, min_periods=52)
    monthly_bx = _bx_regime_from_close(monthly_close, min_periods=24)

    macro_aligned = monthly_bx == "BULLISH" and weekly_bx == "BULLISH"

    return {
        "daily_bx": daily_bx,
        "weekly_bx": weekly_bx,
        "monthly_bx": monthly_bx,
        "macro_aligned": macro_aligned,
    }


def _short_term_zone(row: dict) -> str:
    dist = row.get("dist_ema21_atr")
    if dist is None or pd.isna(dist):
        return "ST_UNKNOWN"
    if dist <= 0.5:
        return "ST_DISCOUNT"
    if dist <= 1.5:
        return "ST_FAIR"
    return "ST_PREMIUM"


def _plan_action(row: dict) -> tuple[str, str, str]:
    big_picture = (
        f"BP_M{row['monthly_bx'][:1]}_W{row['weekly_bx'][:1]}_D{row['daily_bx'][:1]}"
    )
    short_term = _short_term_zone(row)

    if not row["macro_aligned"]:
        if row.get("raw_strategy"):
            return big_picture, short_term, "PLAN_WATCHLIST_MACRO"
        return big_picture, short_term, "PLAN_NO_TRADE_MACRO"

    if row.get("strategy"):
        return big_picture, short_term, "PLAN_ENTRY"

    if row.get("above_sma200") and row.get("ema_cloud_green"):
        return big_picture, short_term, "PLAN_WATCHLIST"

    return big_picture, short_term, "PLAN_NO_TRADE"


def scan_directory(
    data_dir: str,
    mode: str = "core",
    verbose: bool = False,
    top: int = 20,
    strategy: str = "ALL",
    min_dollar_volume: float = 1_000_000.0,
    min_today_dollar_volume: float | None = None,
    use_cache: bool = True,
    refresh_cache: bool = False,
    export_dir: str = "reports/options_scanner",
    export_prefix: str | None = None,
    workers: int = 1,
) -> None:
    results: list[dict] = []
    near_results: list[dict] = []

    raw_universe_count = 0
    stage_universe: list[str] = []
    stage_liquidity: list[str] = []
    stage_today_liquidity: list[str] = []
    stage_context: list[str] = []
    stage_big_picture: list[str] = []
    stage_regime: list[str] = []
    stage_rsi: list[str] = []
    stage_price_action: list[str] = []
    stage_volume: list[str] = []
    stage_strategy: list[str] = []
    failure_reasons: Counter[str] = Counter()

    cache_hits = 0
    cache_misses = 0
    scan_cache_hits = 0
    scan_cache_misses = 0

    spy_df = _load_benchmark_df(data_dir, "SPY")
    xlu_df = _load_benchmark_df(data_dir, "XLU")
    scan_config = {
        "mode": mode,
        "min_dollar_volume": min_dollar_volume,
        "min_today_dollar_volume": min_today_dollar_volume,
        "use_cache": use_cache,
    }

    files = [f for f in os.listdir(data_dir) if f.lower().endswith(".csv")]

    def _process_file(file: str) -> dict:
        out = {
            "raw_count": 1,
            "symbol": file.replace(".csv", "").upper(),
            "cache_hit": 0,
            "cache_miss": 0,
            "scan_cache_hit": 0,
            "scan_cache_miss": 0,
            "source_path": "",
            "stage_liquidity": False,
            "stage_today_liquidity": False,
            "stage_universe": False,
            "stage_context": False,
            "stage_big_picture": False,
            "stage_regime": False,
            "stage_rsi": False,
            "stage_price_action": False,
            "stage_volume": False,
            "row": None,
            "is_setup": False,
            "near_candidate": False,
            "failure_reason": None,
        }

        symbol = out["symbol"]
        path = os.path.join(data_dir, file)
        out["source_path"] = path

        if use_cache and not refresh_cache:
            cached_out = load_scan_result_cache(symbol, path, scan_config)
            if cached_out is not None:
                cached_out["scan_cache_hit"] = 1
                cached_out["scan_cache_miss"] = 0
                return cached_out
            out["scan_cache_miss"] = 1

        try:
            df = _read_symbol_df(path)
        except Exception:
            return out

        indicator_df = None
        if use_cache and not refresh_cache:
            indicator_df = load_indicator_cache(symbol, path, df)
            if indicator_df is not None:
                out["cache_hit"] = 1
            else:
                out["cache_miss"] = 1

        if indicator_df is None:
            indicator_df = compute_indicator_frame(df)
            if use_cache:
                save_indicator_cache(symbol, path, df, indicator_df)

        if (
            "ADV20_USD" in indicator_df.columns
            and len(indicator_df) == len(df)
            and not indicator_df["ADV20_USD"].empty
        ):
            adv20 = indicator_df["ADV20_USD"].iloc[-1]
        else:
            adv20 = avg_dollar_volume(df["Close"], df["Volume"], window=20).iloc[-1]
        liquidity_ok = bool(not pd.isna(adv20) and adv20 >= min_dollar_volume)
        if not liquidity_ok:
            return out
        out["stage_liquidity"] = True

        today_dollar_volume = float(df["Close"].iloc[-1] * df["Volume"].iloc[-1])
        today_liquidity_ok = True
        if min_today_dollar_volume is not None:
            today_liquidity_ok = today_dollar_volume >= min_today_dollar_volume
            if not today_liquidity_ok:
                return out
        out["stage_today_liquidity"] = True

        if len(df) < 300:
            return out
        out["stage_universe"] = True

        context = compute_context(
            df, spy_df=spy_df, xlu_df=xlu_df, indicator_frame=indicator_df
        )
        if (
            context["hv30"] is not None
            and not pd.isna(context["hv30"])
            and context["hv30"] < 30
        ):
            return out
        if context["fvg"] and context["fvg"]["type"] == "BEARISH":
            return out
        out["stage_context"] = True

        setup = evaluate_put_setup(
            df, mode=mode, context=context, indicator_frame=indicator_df
        )
        mtf = _multi_timeframe_bx(df)
        out["stage_big_picture"] = bool(mtf["macro_aligned"])
        out["stage_regime"] = bool(setup.get("above_sma200"))
        out["stage_rsi"] = bool(
            setup.get("rsi_pullback_ok") and not setup.get("no_trade_zone")
        )
        out["stage_price_action"] = bool(setup.get("price_action_ok"))
        out["stage_volume"] = bool(setup.get("volume_ok"))

        raw_strategy = setup.get("strategy")
        strategy = raw_strategy if mtf["macro_aligned"] else None

        row = {
            "symbol": symbol,
            "strategy": strategy,
            "raw_strategy": raw_strategy,
            "close": round(float(df["Close"].iloc[-1]), 2),
            "avg_dollar_volume_20": round(float(adv20), 2)
            if not pd.isna(adv20)
            else None,
            "today_dollar_volume": round(today_dollar_volume, 2),
            "liquidity_ok": liquidity_ok,
            "today_liquidity_ok": today_liquidity_ok,
            "hv30": round(float(context["hv30"]), 2)
            if not pd.isna(context["hv30"])
            else None,
            "above_sma200": setup.get("above_sma200", False),
            "ema_cloud_green": setup.get("ema_cloud_green", False),
            "rsi": round(float(setup.get("rsi")), 2)
            if not pd.isna(setup.get("rsi"))
            else None,
            "rsi_pullback_ok": setup.get("rsi_pullback_ok", False),
            "no_trade_zone": setup.get("no_trade_zone", False),
            "dist_ema21_atr": round(float(setup.get("dist_ema21_atr")), 2)
            if not pd.isna(setup.get("dist_ema21_atr"))
            else None,
            "near_ema21_ok": setup.get("near_ema21_ok", False),
            "price_action_signal": setup.get("price_action_signal", "NONE"),
            "price_action_ok": setup.get("price_action_ok", False),
            "vol_ratio": round(float(setup.get("vol_ratio")), 2)
            if not pd.isna(setup.get("vol_ratio"))
            else None,
            "volume_ok": setup.get("volume_ok", False),
            "rs_spy": round(float(context["rs_spy"]), 3)
            if not pd.isna(context["rs_spy"])
            else None,
            "rs_xlu": round(float(context["rs_xlu"]), 3)
            if not pd.isna(context["rs_xlu"])
            else None,
            "alpha_rotation": bool(context["alpha_rotation"]),
            "target_dte": f"{setup.get('target_dte_min', 15)}-{setup.get('target_dte_max', 45)}",
            "daily_bx": mtf["daily_bx"],
            "weekly_bx": mtf["weekly_bx"],
            "monthly_bx": mtf["monthly_bx"],
            "macro_aligned": mtf["macro_aligned"],
        }
        big_picture, short_term, plan = _plan_action(row)
        row["big_picture"] = big_picture
        row["short_term_picture"] = short_term
        row["my_plan"] = plan
        row["action"] = plan.split(" ", 1)[0]
        rsi_extreme, action_bias, time_bias = _rsi_info_tags(row["rsi"])
        row["rsi_extreme"] = rsi_extreme
        row["action_bias"] = action_bias
        row["time_bias"] = time_bias

        out["row"] = row
        if row["strategy"]:
            out["is_setup"] = True
        else:
            if raw_strategy and not mtf["macro_aligned"]:
                out["failure_reason"] = "macro_not_aligned"
            else:
                out["failure_reason"] = setup.get("primary_failure_reason")
            near_missing = [
                not row["rsi_pullback_ok"],
                not row["near_ema21_ok"],
                not row["price_action_ok"],
                not row["volume_ok"],
            ]
            out["near_candidate"] = bool(
                row["above_sma200"]
                and row["ema_cloud_green"]
                and sum(near_missing) <= 2
            )

        return out

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            iter_out = executor.map(_process_file, files)
            processed = list(iter_out)
    else:
        processed = [_process_file(f) for f in files]

    for out in processed:
        raw_universe_count += out.get("raw_count", 0)
        cache_hits += out.get("cache_hit", 0)
        cache_misses += out.get("cache_miss", 0)
        scan_cache_hits += out.get("scan_cache_hit", 0)
        scan_cache_misses += out.get("scan_cache_miss", 0)
        symbol = out.get("symbol", "")

        if out.get("stage_liquidity", False):
            stage_liquidity.append(symbol)
        if out.get("stage_today_liquidity", False):
            stage_today_liquidity.append(symbol)
        if out.get("stage_universe", False):
            stage_universe.append(symbol)
        if out.get("stage_context", False):
            stage_context.append(symbol)
        if out.get("stage_big_picture", False):
            stage_big_picture.append(symbol)
        if out.get("stage_regime", False):
            stage_regime.append(symbol)
        if out.get("stage_rsi", False):
            stage_rsi.append(symbol)
        if out.get("stage_price_action", False):
            stage_price_action.append(symbol)
        if out.get("stage_volume", False):
            stage_volume.append(symbol)

        row = out.get("row")
        if row is None:
            continue
        if out.get("is_setup", False):
            stage_strategy.append(symbol)
            results.append(row)
        else:
            if out.get("failure_reason"):
                failure_reasons[out["failure_reason"]] += 1
            if out.get("near_candidate", False):
                near_results.append(row)

        source_path = out.get("source_path")
        if (
            use_cache
            and source_path
            and (refresh_cache or out.get("scan_cache_hit", 0) == 0)
        ):
            save_scan_result_cache(symbol, source_path, scan_config, out)

    df_results = pd.DataFrame(results)
    if not df_results.empty:
        required_cols_defaults = {
            "big_picture": "BP_MU_WU_DU",
            "monthly_bx": "UNKNOWN",
            "weekly_bx": "UNKNOWN",
            "daily_bx": "UNKNOWN",
            "macro_aligned": False,
            "short_term_picture": "ST_UNKNOWN",
            "my_plan": "PLAN_UNKNOWN",
            "today_dollar_volume": None,
            "rsi_extreme": "UNKNOWN",
            "action_bias": "NONE",
            "time_bias": "BUY_OPT:90-720D | SELL_OPT:7-42D",
        }
        for col, default in required_cols_defaults.items():
            if col not in df_results.columns:
                df_results[col] = default

        df_results["score"] = df_results.apply(compute_final_score, axis=1)
        df_results = df_results.sort_values("score", ascending=False).reset_index(
            drop=True
        )

        if strategy != "ALL":
            df_results = df_results[df_results["strategy"] == strategy].reset_index(
                drop=True
            )

        if top > 0:
            df_results = df_results.head(top)

        print("\nSETUPS ENCONTRADOS")
        print(f"Filtro: strategy={strategy} | top={top}")
        print(
            df_results[
                [
                    "symbol",
                    "strategy",
                    "score",
                    "close",
                    "avg_dollar_volume_20",
                    "today_dollar_volume",
                    "above_sma200",
                    "ema_cloud_green",
                    "rsi",
                    "rsi_pullback_ok",
                    "no_trade_zone",
                    "dist_ema21_atr",
                    "vol_ratio",
                    "volume_ok",
                    "rs_spy",
                    "rs_xlu",
                    "alpha_rotation",
                    "price_action_signal",
                    "big_picture",
                    "monthly_bx",
                    "weekly_bx",
                    "daily_bx",
                    "macro_aligned",
                    "rsi_extreme",
                    "action_bias",
                    "time_bias",
                    "short_term_picture",
                    "my_plan",
                ]
            ]
            .rename(
                columns={
                    "symbol": "Symbol",
                    "strategy": "Operation",
                    "score": "Score",
                    "close": "Close",
                    "avg_dollar_volume_20": "ADV20_USD",
                    "today_dollar_volume": "TODAY_DOLLAR_VOLUME",
                    "above_sma200": "SMA200_OK",
                    "ema_cloud_green": "CloudGreen",
                    "rsi": "RSI14",
                    "rsi_pullback_ok": "RSIPullback",
                    "no_trade_zone": "NoTradeZone",
                    "dist_ema21_atr": "DistEMA21ATR",
                    "vol_ratio": "VolRatio",
                    "volume_ok": "VolumeOK",
                    "rs_spy": "RS_SPY",
                    "rs_xlu": "RS_XLU",
                    "alpha_rotation": "Alpha",
                    "price_action_signal": "PriceAction",
                    "big_picture": "BigPic",
                    "monthly_bx": "BX_Monthly",
                    "weekly_bx": "BX_Weekly",
                    "daily_bx": "BX_Daily",
                    "macro_aligned": "MacroAligned",
                    "rsi_extreme": "RSI_Extreme",
                    "action_bias": "Action_Bias",
                    "time_bias": "Time_Bias",
                    "short_term_picture": "ShortTerm",
                    "my_plan": "MyPlan",
                }
            )
            .to_string(index=False)
        )

        if not df_results.empty:
            print("\nRESUMO POR OPERACAO")
            for strategy_name, count in df_results["strategy"].value_counts().items():
                print(f"{strategy_name}: {count}")
        else:
            print("\nNenhum setup encontrado apos aplicar os filtros.")
    else:
        print("\nNenhum setup encontrado para os filtros atuais.")

    if verbose:
        print("\nETAPAS DO SCAN")
        cache_mode = (
            "disabled" if not use_cache else ("refresh" if refresh_cache else "normal")
        )
        print(f"Cache mode:                {cache_mode}")
        print(f"Workers:                   {workers}")
        print(f"Universo bruto (CSV):      {raw_universe_count} ativos")
        print(f"Passou liquidez (ADV20):   {len(stage_liquidity)}")
        if min_today_dollar_volume is not None:
            print(f"Passou liquidez hoje:      {len(stage_today_liquidity)}")
        print(f"Universo analisavel:       {len(stage_universe)}")
        print(f"Apos contexto:             {len(stage_context)}")
        print(f"Macro alinhado (M>W>D):    {len(stage_big_picture)}")
        print(f"Passou SMA200 + regime:    {len(stage_regime)}")
        print(f"Passou RSI pullback:       {len(stage_rsi)}")
        print(f"Passou Price Action:       {len(stage_price_action)}")
        volume_label = "1.5x" if mode == "core" else "1.2x"
        print(f"Passou Volume {volume_label}:        {len(stage_volume)}")
        print(f"Setups finais:             {len(stage_strategy)}")
        if use_cache:
            print(f"Scan cache hits/misses:    {scan_cache_hits}/{scan_cache_misses}")
            print(f"Indicator cache hits/miss: {cache_hits}/{cache_misses}")

        alpha_count = sum(1 for r in results if r.get("alpha_rotation"))
        print(f"Alpha rotation (setups):   {alpha_count}")

        if failure_reasons:
            print("\nTop Failure Reasons")
            for reason, qty in failure_reasons.most_common(8):
                print(f"{reason}: {qty}")

        print("\nAtivos por etapa")
        print("Liquidez OK:", stage_liquidity[:20])
        if min_today_dollar_volume is not None:
            print("Liquidez Hoje OK:", stage_today_liquidity[:20])
        print("Contexto OK:", stage_context[:20])
        print("Macro OK:", stage_big_picture[:20])
        print("Regime OK:", stage_regime[:20])
        print("RSI OK:", stage_rsi[:20])
        print("PriceAction OK:", stage_price_action[:20])
        print("Volume OK:", stage_volume[:20])
        print("Setups:", stage_strategy[:20])

        if near_results:
            df_near = (
                pd.DataFrame(near_results)
                .sort_values(["dist_ema21_atr", "rsi"], ascending=[True, True])
                .head(20)
            )
            if "rsi_extreme" not in df_near.columns:
                df_near["rsi_extreme"] = "UNKNOWN"
            print("\nQUASE SETUPS (monitorar)")
            print(
                df_near[
                    [
                        "symbol",
                        "close",
                        "rsi",
                        "dist_ema21_atr",
                        "vol_ratio",
                        "price_action_signal",
                        "alpha_rotation",
                        "rsi_extreme",
                    ]
                ]
                .rename(
                    columns={
                        "symbol": "Symbol",
                        "close": "Close",
                        "rsi": "RSI14",
                        "dist_ema21_atr": "DistEMA21ATR",
                        "vol_ratio": "VolRatio",
                        "price_action_signal": "PriceAction",
                        "alpha_rotation": "Alpha",
                        "rsi_extreme": "RSI_Extreme",
                    }
                )
                .to_string(index=False)
            )

    os.makedirs(export_dir, exist_ok=True)
    run_id = export_prefix or f"scan_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    setups_out = os.path.join(export_dir, f"{run_id}_setups.csv")
    near_out = os.path.join(export_dir, f"{run_id}_near_setups.csv")
    summary_out = os.path.join(export_dir, f"{run_id}_summary.json")

    df_results.to_csv(setups_out, index=False)
    pd.DataFrame(near_results).to_csv(near_out, index=False)

    summary = {
        "run_id": run_id,
        "mode": mode,
        "top": top,
        "strategy_filter": strategy,
        "min_dollar_volume": min_dollar_volume,
        "min_today_dollar_volume": min_today_dollar_volume,
        "raw_universe_count": raw_universe_count,
        "liquidity_pass_count": len(stage_liquidity),
        "today_liquidity_pass_count": len(stage_today_liquidity),
        "analyzable_count": len(stage_universe),
        "context_pass_count": len(stage_context),
        "macro_aligned_count": len(stage_big_picture),
        "regime_pass_count": len(stage_regime),
        "rsi_pass_count": len(stage_rsi),
        "price_action_pass_count": len(stage_price_action),
        "volume_pass_count": len(stage_volume),
        "setups_count": len(stage_strategy),
        "near_setups_count": len(near_results),
        "failure_reasons": dict(failure_reasons),
        "use_cache": use_cache,
        "refresh_cache": refresh_cache,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "scan_cache_hits": scan_cache_hits,
        "scan_cache_misses": scan_cache_misses,
        "generated_at": datetime.now().isoformat(),
    }
    if results:
        action_counts = Counter(r.get("action", "UNKNOWN") for r in results)
        summary["action_counts"] = dict(action_counts)
    with open(summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nExported: {setups_out}")
    print(f"Exported: {near_out}")
    print(f"Exported: {summary_out}")


# =========================
# MAIN CLI
# =========================

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Options Tech Scanner")

    parser.add_argument(
        "--data-dir", type=str, required=True, help="Diretorio dos CSVs"
    )
    parser.add_argument("--scan", action="store_true", help="Executar scan diario")
    parser.add_argument("--backtest", action="store_true", help="Executar backtest")
    parser.add_argument("--mode", choices=["core", "relaxed"], default="core")
    parser.add_argument("--lookahead", type=int, default=30)
    parser.add_argument(
        "--verbose", action="store_true", help="Imprime ativos por etapa do filtro"
    )
    parser.add_argument(
        "--top", type=int, default=20, help="Limite de resultados exibidos no scan"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Numero de workers para processamento paralelo no scan (1 = serial)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Desabilita o cache de indicadores para o scan",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Recalcula e sobrescreve cache de indicadores",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default="reports/options_scanner",
        help="Diretorio para exportar resultados do scan",
    )
    parser.add_argument(
        "--export-prefix",
        type=str,
        default=None,
        help="Prefixo de arquivo para exportacao (opcional)",
    )
    parser.add_argument(
        "--min-dollar-volume",
        type=float,
        default=1_000_000.0,
        help="Filtro minimo de liquidez por media de volume financeiro diario (ADV20 em USD)",
    )
    parser.add_argument(
        "--min-today-dollar-volume",
        type=float,
        default=None,
        help="Filtro minimo opcional para volume financeiro do ultimo dia (Close*Volume em USD)",
    )
    parser.add_argument(
        "--strategy",
        choices=["ALL", "CSP", "BULL_PUT_SPREAD"],
        default="ALL",
        help="Filtrar scan por estrategia",
    )

    args = parser.parse_args()

    if args.scan:
        print(f"\nSCAN ({args.mode.upper()})")
        scan_directory(
            args.data_dir,
            mode=args.mode,
            verbose=args.verbose,
            top=args.top,
            strategy=args.strategy,
            min_dollar_volume=args.min_dollar_volume,
            min_today_dollar_volume=args.min_today_dollar_volume,
            use_cache=not args.no_cache,
            refresh_cache=args.refresh_cache,
            export_dir=args.export_dir,
            export_prefix=args.export_prefix,
            workers=max(1, args.workers),
        )

    if args.backtest:
        print(f"\nBACKTEST ({args.mode.upper()})")
        events, diagnostics = run_backtest_mode(
            data_dir=args.data_dir,
            lookahead=args.lookahead,
            mode=args.mode,
            include_diagnostics=True,
        )

        from options_tech_scanner.metrics import detailed_backtest_report

        report = detailed_backtest_report(events, diagnostics=diagnostics)

        print(
            f"Total trades: {report['total_trades']} | "
            f"Overall win rate: {report['overall_win_rate']:.2%}"
        )

        print("\nBy Strategy")
        for strat, stats in report["strategy_summary"].items():
            print(
                f"{strat}: "
                f"{stats['trades']} trades | "
                f"Win Rate = {stats['win_rate']:.2%}"
            )

        print("\nAlpha Split")
        for name, stats in report["alpha_split"].items():
            print(
                f"{name}: "
                f"{stats['trades']} trades | "
                f"Win Rate = {stats['win_rate']:.2%}"
            )

        print("\nPrice Action Breakdown")
        for signal, stats in report["price_action_breakdown"].items():
            print(
                f"{signal}: "
                f"{stats['trades']} trades | "
                f"Win Rate = {stats['win_rate']:.2%}"
            )

        if report["filter_pass_rates"]:
            print("\nFilter Pass Rates (bar-level)")
            for filter_name, rate in report["filter_pass_rates"].items():
                print(f"{filter_name}: {rate:.2%}")
