MOCK_ACCOUNTS_RESPONSE = [
    {
        "accountId": "U1234567",
        "accountTitle": "Individual",
        "type": "INDIVIDUAL",
    }
]

MOCK_SUMMARY_RESPONSE = {
    "netliquidation": {"amount": 50000.0, "currency": "USD"},
    "totalcashvalue": {"amount": 10000.0, "currency": "USD"},
    "buyingpower": {"amount": 20000.0, "currency": "USD"},
    "initmarginreq": {"amount": 5000.0, "currency": "USD"},
    "maintmarginreq": {"amount": 3000.0, "currency": "USD"},
    "excessliquidity": {"amount": 45000.0, "currency": "USD"},
}

MOCK_POSITIONS_RESPONSE = [
    {
        "acctId": "U1234567",
        "conid": 265598,
        "contractDesc": "AAPL",
        "ticker": "AAPL",
        "position": 100.0,
        "mktPrice": 180.0,
        "mktValue": 18000.0,
        "currency": "USD",
        "avgCost": 150.0,
        "avgPrice": 150.0,
        "realizedPnl": 0.0,
        "unrealizedPnl": 3000.0,
        "assetClass": "STK",
        "expiry": None,
        "putOrCall": None,
        "strike": 0.0,
        "delta": None,
    },
    {
        "acctId": "U1234567",
        "conid": 999001,
        "contractDesc": "PEP 15JAN2027 140 P",
        "ticker": "PEP",
        "position": -1.0,
        "mktPrice": 2.86,
        "mktValue": -286.0,
        "currency": "USD",
        "avgCost": 2.86,
        "avgPrice": 2.86,
        "realizedPnl": 0.0,
        "unrealizedPnl": 0.0,
        "assetClass": "OPT",
        "expiry": "20270115",
        "putOrCall": "P",
        "strike": 140.0,
        "delta": -0.32,
        "undPrice": 152.0,
    },
]

MOCK_LEDGER_RESPONSE = {
    "BASE": {"cashbalance": 10000.0, "settledcash": 9800.0, "currency": "USD"},
    "USD": {"cashbalance": 10000.0, "settledcash": 9800.0, "currency": "USD"},
}
