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
