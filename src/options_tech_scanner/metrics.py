def win_rate(events):
    if not events:
        return 0.0
    wins = sum(e["win"] for e in events)
    return wins / len(events)


def summary_by_strategy(events):
    summary = {}
    for strat in ["CSP", "BULL_PUT_SPREAD"]:
        subset = [e for e in events if e["strategy"] == strat]
        summary[strat] = {"trades": len(subset), "win_rate": win_rate(subset)}
    return summary


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def detailed_backtest_report(events, diagnostics=None):
    total_trades = len(events)
    overall_win = win_rate(events)

    strategy_summary = summary_by_strategy(events)

    alpha_events = [e for e in events if e.get("alpha_rotation")]
    non_alpha_events = [e for e in events if not e.get("alpha_rotation")]

    alpha_split = {
        "alpha": {"trades": len(alpha_events), "win_rate": win_rate(alpha_events)},
        "non_alpha": {
            "trades": len(non_alpha_events),
            "win_rate": win_rate(non_alpha_events),
        },
    }

    price_action_breakdown = {}
    for signal in ["BULLISH_PIN_BAR", "BULLISH_ENGULFING", "NONE"]:
        subset = [e for e in events if e.get("price_action_signal") == signal]
        price_action_breakdown[signal] = {
            "trades": len(subset),
            "win_rate": win_rate(subset),
        }

    filter_pass_rates = {}
    if diagnostics:
        bars = diagnostics.get("bars_evaluated", 0)
        filter_pass_rates = {
            "above_sma200": _rate(diagnostics.get("pass_above_sma200", 0), bars),
            "ema_cloud_green": _rate(diagnostics.get("pass_ema_cloud_green", 0), bars),
            "rsi_pullback": _rate(diagnostics.get("pass_rsi_pullback", 0), bars),
            "not_no_trade_zone": _rate(
                diagnostics.get("pass_not_no_trade_zone", 0), bars
            ),
            "near_ema21": _rate(diagnostics.get("pass_near_ema21", 0), bars),
            "price_action": _rate(diagnostics.get("pass_price_action", 0), bars),
            "volume_1_5x": _rate(diagnostics.get("pass_volume", 0), bars),
            "alpha_rotation": _rate(diagnostics.get("pass_alpha_rotation", 0), bars),
            "final_setup": _rate(diagnostics.get("final_setups", 0), bars),
        }

    return {
        "total_trades": total_trades,
        "overall_win_rate": overall_win,
        "strategy_summary": strategy_summary,
        "alpha_split": alpha_split,
        "price_action_breakdown": price_action_breakdown,
        "diagnostics": diagnostics or {},
        "filter_pass_rates": filter_pass_rates,
    }
