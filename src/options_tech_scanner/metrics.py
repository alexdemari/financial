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
