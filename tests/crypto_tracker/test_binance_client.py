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
