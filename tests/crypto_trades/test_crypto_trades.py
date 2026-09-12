import csv
from pathlib import Path

import pytest

from crypto_trades.classifier import classify, get_asset
from crypto_trades.cost_basis import compute_cost_basis
from crypto_trades.models import CryptoTrade, EarnRecord
from crypto_trades.parser import parse_export_csv
from crypto_trades.ptax_enricher import enrich_earnings, enrich_trades
from crypto_trades.store import TRADE_FIELDS, append_deduplicated
from crypto_trades.sync import build_known_execution_ids_by_symbol, fetch_new_trades


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "id": "1",
        "datetime_tz_GMT-03:00": "2025-01-15 10:00:00-03:00",
        "type": "Trade",
        "market_model_type": "SPOT",
        "order_type": "MARKET",
        "sent_amount": "100",
        "sent_currency": "USDT",
        "sent_value_BRL": "590",
        "received_amount": "1",
        "received_currency": "ADA",
        "received_value_BRL": "590",
        "fee_amount": "0.1",
        "fee_currency": "BNB",
        "fee_value_BRL": "2",
    }
    row.update(overrides)
    return row


def _write_export(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _trade(
    trade_type: str,
    quantity: float,
    value_brl_ptax: float,
    *,
    asset: str = "BTC",
    date: str = "2025-01-01",
) -> CryptoTrade:
    return CryptoTrade(
        "id",
        date,
        f"{date}T10:00:00-03:00",
        trade_type,
        asset,
        quantity,
        0,
        0,
        0,
        "",
        0,
        value_brl_ptax,
        5.0,
        value_brl_ptax,
    )


def test_classifier_usdt_sent_is_buy():
    assert classify(_row()) == "BUY"
    assert get_asset(_row(), "BUY") == "ADA"


def test_classifier_usdt_received_is_sell():
    row = _row(
        sent_currency="ETH",
        sent_amount="2",
        received_currency="USDT",
        received_amount="4000",
    )
    assert classify(row) == "SELL"
    assert get_asset(row, "SELL") == "ETH"


def test_classifier_crypto_to_crypto_is_swap():
    row = _row(sent_currency="BTC", received_currency="ETH")
    assert classify(row) == "SWAP"


def test_classifier_stablecoin_to_stablecoin_is_non_taxable_swap():
    row = _row(sent_currency="USDT", received_currency="USDC")
    assert classify(row) == "STABLE_SWAP"


def test_classifier_earn_receive_is_separate():
    assert classify(_row(type="Receive", market_model_type="EARN")) == "EARN"


def test_parser_separates_trades_earn_and_persists_deposits(tmp_path: Path):
    export = tmp_path / "binance.csv"
    _write_export(
        export,
        [_row(id=str(index)) for index in range(5)]
        + [
            _row(id=f"earn-{index}", type="Receive", market_model_type="EARN")
            for index in range(3)
        ]
        + [
            _row(id=f"deposit-{index}", type="Deposit", market_model_type="FIAT")
            for index in range(2)
        ],
    )
    trades, earnings = parse_export_csv(export)
    assert len(trades) == 7
    assert [trade.trade_type for trade in trades[-2:]] == [
        "DEPOSIT_FIAT",
        "DEPOSIT_FIAT",
    ]
    assert len(earnings) == 3


def test_parser_persists_external_transfers(tmp_path: Path):
    export = tmp_path / "transfers.csv"
    _write_export(
        export,
        [
            _row(type="Send", sent_currency="ETH", received_currency=""),
            _row(
                type="Receive",
                market_model_type="CRYPTO_DEPOSIT",
                sent_currency="",
                received_currency="ETH",
            ),
        ],
    )

    trades, _ = parse_export_csv(export)

    assert [trade.trade_type for trade in trades] == ["SEND", "RECEIVE_EXTERNAL"]


def test_parser_expands_swap_to_buy_and_sell(tmp_path: Path):
    export = tmp_path / "binance.csv"
    _write_export(
        export, [_row(id="swap", sent_currency="BTC", received_currency="ETH")]
    )
    trades, _ = parse_export_csv(export)
    assert [(trade.trade_id, trade.trade_type) for trade in trades] == [
        ("swap_A", "SWAP_SELL"),
        ("swap_B", "SWAP_BUY"),
    ]


def test_store_deduplicates_by_trade_id(tmp_path: Path):
    path = tmp_path / "trades.csv"
    records = [_trade("BUY", 1, 100)]
    assert append_deduplicated(path, records, TRADE_FIELDS) == 1
    assert append_deduplicated(path, records, TRADE_FIELDS) == 0
    assert len(path.read_text().splitlines()) == 2


def test_cost_basis_cmm_after_two_buys():
    basis = compute_cost_basis(
        [_trade("BUY", 1, 300_000), _trade("BUY", 0.5, 165_000, date="2025-01-02")]
    )
    assert basis["BTC"].quantity == 1.5
    assert basis["BTC"].avg_cost_brl_ptax == 310_000


def test_cost_basis_is_unchanged_after_sell():
    basis = compute_cost_basis(
        [
            _trade("BUY", 2, 20_000, asset="ETH"),
            _trade("SELL", 1, 10_000, asset="ETH", date="2025-01-02"),
        ]
    )
    assert basis["ETH"].quantity == 1
    assert basis["ETH"].avg_cost_brl_ptax == 10_000


def test_ptax_enricher_populates_official_brl_value():
    trade = _trade("BUY", 1, 0)
    trade.total_usdt = 100
    enrich_trades([trade], lookup=lambda _: 5.89)
    assert trade.ptax_bcb == 5.89
    assert trade.value_brl_ptax == pytest.approx(589)


def test_ptax_enricher_values_usdt_earnings_at_ptax():
    earning = EarnRecord("earn", "2025-01-01", "USDT", 2, 10)
    enrich_earnings([earning], lookup=lambda _: 5.89)
    assert earning.value_brl_ptax == pytest.approx(11.78)


def test_earn_records_do_not_enter_trade_history(tmp_path: Path):
    export = tmp_path / "earn.csv"
    _write_export(export, [_row(type="Receive", market_model_type="EARN")])
    trades, earnings = parse_export_csv(export)
    assert trades == []
    assert len(earnings) == 1


def test_sync_requests_after_last_known_execution_id():
    class Client:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int | None]] = []

        def get_my_trades(
            self, symbol: str, from_id: int | None = None
        ) -> list[dict[str, object]]:
            self.calls.append((symbol, from_id))
            return [
                {
                    "id": 8,
                    "time": 1_736_942_400_000,
                    "isBuyer": True,
                    "qty": "1",
                    "price": "100",
                    "quoteQty": "100",
                }
            ]

    client = Client()
    trades = fetch_new_trades(client, ["BTCUSDT"], {"BTCUSDT": {"7"}})
    assert client.calls == [("BTCUSDT", 8)]
    assert trades[0].trade_id == "api_BTCUSDT_8"


def test_sync_skips_failed_symbol_and_returns_other_symbols():
    class Client:
        def get_my_trades(
            self, symbol: str, from_id: int | None = None
        ) -> list[dict[str, object]]:
            if symbol == "BTCUSDT":
                raise RuntimeError("Binance unavailable")
            return [
                {
                    "id": 9,
                    "time": 1_736_942_400_000,
                    "isBuyer": True,
                    "qty": "1",
                    "price": "100",
                    "quoteQty": "100",
                }
            ]

    trades = fetch_new_trades(
        Client(), ["BTCUSDT", "ETHUSDT"], {"BTCUSDT": set(), "ETHUSDT": set()}
    )

    assert [trade.trade_id for trade in trades] == ["api_ETHUSDT_9"]


def test_sync_skips_execution_already_imported_from_csv():
    class Client:
        def get_my_trades(
            self, symbol: str, from_id: int | None = None
        ) -> list[dict[str, object]]:
            return [
                {
                    "id": 7,
                    "time": 1_736_942_400_000,
                    "isBuyer": True,
                    "qty": "1",
                    "price": "100",
                    "quoteQty": "100",
                }
            ]

    trades = fetch_new_trades(Client(), ["BTCUSDT"], {"BTCUSDT": {"7"}})

    assert trades == []


def test_sync_keeps_same_numeric_id_from_different_symbol_and_source():
    existing_trades = [
        CryptoTrade(
            "9",
            "2025-01-01",
            "2025-01-01T10:00:00-03:00",
            "BUY",
            "BTC",
            1,
            100,
            100,
            0,
            "",
            0,
            0,
            source="export",
        ),
        CryptoTrade(
            "api_BTCUSDT_7",
            "2025-01-01",
            "2025-01-01T10:00:00-03:00",
            "BUY",
            "BTC",
            1,
            100,
            100,
            0,
            "",
            0,
            0,
            source="api",
        ),
    ]

    class Client:
        def get_my_trades(
            self, symbol: str, from_id: int | None = None
        ) -> list[dict[str, object]]:
            return [
                {
                    "id": 9,
                    "time": 1_736_942_400_000,
                    "isBuyer": True,
                    "qty": "1",
                    "price": "100",
                    "quoteQty": "100",
                }
            ]

    known_execution_ids = build_known_execution_ids_by_symbol(
        existing_trades, ["BTCUSDT", "ETHUSDT"]
    )
    trades = fetch_new_trades(Client(), ["ETHUSDT"], known_execution_ids)

    assert known_execution_ids == {"BTCUSDT": {"7", "9"}, "ETHUSDT": set()}
    assert [trade.trade_id for trade in trades] == ["api_ETHUSDT_9"]
