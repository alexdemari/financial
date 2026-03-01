from options_tech_scanner.loader import load_csv
from options_tech_scanner.setups import classify_put_strategy
from options_tech_scanner.scorer import score_setup
from options_tech_scanner.events import detect_setups


def process_symbol_scan(args):
    symbol, path = args

    try:
        df = load_csv(path)
        if len(df) < 300:
            return None

        setup = classify_put_strategy(df)
        if setup is None:
            return None

        setup["symbol"] = symbol
        setup["score"] = score_setup(setup)
        return setup

    except Exception:
        return None


def process_symbol_backtest(args):
    symbol, path, lookahead = args

    try:
        df = load_csv(path)
        if len(df) < 500:
            return []

        events = detect_setups(df, lookahead)
        for e in events:
            e["symbol"] = symbol
        return events

    except Exception:
        return []
