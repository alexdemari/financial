import json
from pathlib import Path

from crypto_irpf.apuracao import apurar_ano
from crypto_irpf.earn import EarnSummary
from crypto_irpf.report import format_section
from crypto_trades.cost_basis import compute_cost_basis_with_history
from crypto_trades.models import CryptoTrade
from crypto_trades.store import TRADE_FIELDS, append_deduplicated
from irpf_report.main import _include_crypto_section


def test_zerada_carteira_is_empty_in_bens_e_direitos():
    report = format_section(
        [], EarnSummary(0, {}), 2026, {"BTC": {"quantity": 0, "cost_brl": 0}}
    )
    assert "| (nenhum) | — | — |" in report


def test_report_includes_monthly_sale_details():
    trade = CryptoTrade(
        "sell",
        "2026-01-01",
        "2026-01-01T10:00:00-03:00",
        "SELL",
        "BTC",
        1,
        0,
        0,
        0,
        "",
        0,
        50_000,
        5,
        50_000,
    )
    trades = [
        CryptoTrade(
            "buy",
            "2025-01-01",
            "2025-01-01T10:00:00-03:00",
            "BUY",
            "BTC",
            1,
            0,
            0,
            0,
            "",
            0,
            30_000,
            5,
            30_000,
        ),
        trade,
    ]
    _, snapshots = compute_cost_basis_with_history(trades)
    history = {str(snapshot["trade_id"]): snapshot["assets"] for snapshot in snapshots}
    monthly = apurar_ano(trades, 2026, history)
    report = format_section(monthly, EarnSummary(0, {}), 2026, {})
    assert "TRIBUTÁVEL" in report
    assert "2026-01-01" in report


def test_consolidated_irpf_includes_crypto_section_when_history_exists(tmp_path: Path):
    trades_path = tmp_path / "trades.csv"
    earn_path = tmp_path / "earn.csv"
    cost_basis_path = tmp_path / "cost_basis.json"
    trades = [
        CryptoTrade(
            "buy",
            "2025-01-01",
            "2025-01-01T10:00:00-03:00",
            "BUY",
            "BTC",
            1,
            0,
            0,
            0,
            "",
            0,
            30_000,
            5,
            30_000,
        ),
        CryptoTrade(
            "sell",
            "2026-01-01",
            "2026-01-01T10:00:00-03:00",
            "SELL",
            "BTC",
            1,
            0,
            0,
            0,
            "",
            0,
            50_000,
            5,
            50_000,
        ),
    ]
    append_deduplicated(trades_path, trades, TRADE_FIELDS)
    basis, history = compute_cost_basis_with_history(trades)
    cost_basis_path.write_text(
        json.dumps(
            {
                "assets": {asset: vars(item) for asset, item in basis.items()},
                "history": history,
            }
        )
    )

    section = _include_crypto_section(2026, trades_path, earn_path, cost_basis_path)

    assert "## Criptoativos Binance" in section
    assert "TRIBUTÁVEL" in section
