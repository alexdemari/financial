def score_setup(setup):
    score = 0

    # RSI ideal
    score += max(0, 60 - abs(50 - setup["rsi"]))

    # Proximidade do suporte (penaliza longe demais)
    score += max(0, 2.0 - setup["distance_to_support_atr"]) * 20

    # Volatilidade eficiente
    score += min(setup["volatility_ratio"], 1.5) * 15

    # Bônus por risco limitado
    if setup["strategy"] == "BULL_PUT_SPREAD":
        score += 10

    return round(score, 2)
