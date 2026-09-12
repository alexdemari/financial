from crypto_tracker.binance_client import BinanceReadOnlyClient


def test_get_prices_uses_one_batched_ticker_request(monkeypatch):
    client = BinanceReadOnlyClient("key", "secret")
    requests = []

    def fake_request(endpoint, params, signed):
        requests.append((endpoint, params, signed))
        return [
            {"symbol": "BTCUSDT", "price": "60000"},
            {"symbol": "ETHUSDT", "price": "3000"},
        ]

    monkeypatch.setattr(client, "_request", fake_request)

    assert client.get_prices(["BTCUSDT", "ETHUSDT"]) == {
        "BTCUSDT": 60000.0,
        "ETHUSDT": 3000.0,
    }
    assert requests == [("/api/v3/ticker/price", {}, False)]


def test_get_earn_balances_combines_flexible_and_locked_positions(monkeypatch):
    client = BinanceReadOnlyClient("key", "secret")
    requests = []

    def fake_signed_request(endpoint, params):
        requests.append((endpoint, params))
        if endpoint.endswith("flexible/position"):
            return {"rows": [{"asset": "USDT", "totalAmount": "100"}], "total": 1}
        return {"rows": [{"asset": "BTC", "amount": "0.25"}], "total": 1}

    monkeypatch.setattr(client, "_signed_request", fake_signed_request)

    assert client.get_earn_balances() == [
        {"asset": "USDT", "amount": 100.0},
        {"asset": "BTC", "amount": 0.25},
    ]
    assert [endpoint for endpoint, _ in requests] == [
        "/sapi/v1/simple-earn/flexible/position",
        "/sapi/v1/simple-earn/locked/position",
    ]


def test_get_my_trades_paginates_after_last_execution_id(monkeypatch):
    client = BinanceReadOnlyClient("key", "secret")
    requests = []
    first_page = [{"id": execution_id} for execution_id in range(1, 1001)]

    def fake_signed_request(endpoint, params):
        requests.append((endpoint, params))
        if params.get("fromId") is None:
            return first_page
        return [{"id": 1001}]

    monkeypatch.setattr(client, "_signed_request", fake_signed_request)

    trades = client.get_my_trades("BTCUSDT")

    assert len(trades) == 1001
    assert requests == [
        ("/api/v3/myTrades", {"symbol": "BTCUSDT", "limit": 1000}),
        (
            "/api/v3/myTrades",
            {"symbol": "BTCUSDT", "limit": 1000, "fromId": 1001},
        ),
    ]
