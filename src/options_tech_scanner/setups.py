def classify_put_strategy(
    *,
    bullish: bool,
    rsi_val: float,
    dist_atr: float,
    vol_ratio: float,
    mode: str = "core"
) -> str | None:
    if mode == "core":
        min_dist = 0.8
    elif mode == "relaxed":
        min_dist = 0.45
    else:
        raise ValueError("mode inválido")

    # =========================
    # CASH SECURED PUT
    # =========================
    if (
        bullish
        and min_dist <= dist_atr < 3.5
        and vol_ratio < 1.0
        and 35 <= rsi_val <= 60
    ):
        return "CSP"

    # =========================
    # BULL PUT SPREAD
    # =========================
    if (
        min_dist <= dist_atr < 1.2
        and vol_ratio < 1.5
        and 40 <= rsi_val <= 65
    ):
        return "BULL_PUT_SPREAD"

    return None
