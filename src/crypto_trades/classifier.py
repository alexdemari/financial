"""Classify Binance transaction-history rows without doing I/O."""

FIAT_CURRENCIES = {"BRL", "USD", "EUR"}
STABLE_COINS = {"USDT", "USDC", "BUSD", "TUSD"}


def classify(row: dict[str, str]) -> str:
    """Return the canonical operation type for one Binance export row."""
    transaction_type = row.get("type", "").strip()
    sent = row.get("sent_currency", "").strip().upper()
    received = row.get("received_currency", "").strip().upper()
    market_model_type = row.get("market_model_type", "").strip().upper()
    if transaction_type == "Receive" and market_model_type == "EARN":
        return "EARN"
    if transaction_type == "Deposit" and market_model_type == "FIAT":
        return "DEPOSIT_FIAT"
    if transaction_type == "Send":
        return "SEND"
    if transaction_type == "Receive" and market_model_type == "CRYPTO_DEPOSIT":
        return "RECEIVE_EXTERNAL"
    if sent in STABLE_COINS and received in STABLE_COINS:
        return "STABLE_SWAP"
    if sent in STABLE_COINS | FIAT_CURRENCIES:
        return "BUY"
    if received in STABLE_COINS | FIAT_CURRENCIES:
        return "SELL"
    if sent and received:
        return "SWAP"
    return "UNKNOWN"


def get_asset(row: dict[str, str], trade_type: str) -> str:
    """Return the crypto asset affected by a classified operation."""
    if trade_type in {"BUY", "SWAP_BUY"}:
        return row.get("received_currency", "").upper()
    if trade_type in {"SELL", "SWAP_SELL"}:
        return row.get("sent_currency", "").upper()
    return (row.get("received_currency") or row.get("sent_currency") or "").upper()
