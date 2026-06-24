from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ibkr_positions.main import main
from ibkr_positions.models import AccountSummary, Portfolio
from ibkr_positions.snapshot_store import HISTORY_PATH


def test_snapshot_write_failure_warns_and_still_writes_reports(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    portfolio = Portfolio(
        account_id="U123456",
        as_of="2026-06-24T10:00:00",
        summary=AccountSummary(
            net_liquidation=50000.0,
            total_cash=12000.0,
            buying_power=100000.0,
            initial_margin=12500.0,
            maintenance_margin=10000.0,
            excess_liquidity=37500.0,
        ),
        cash=[],
        positions=[],
    )
    client = MagicMock()
    client.get_portfolio.return_value = portfolio
    original_write_text = Path.write_text

    def write_text_or_fail(path: Path, *args, **kwargs) -> int:
        if path == HISTORY_PATH:
            raise OSError("history is read-only")
        return original_write_text(path, *args, **kwargs)

    with (
        patch("ibkr_positions.main.IBKRClient", return_value=client),
        patch.object(Path, "write_text", autospec=True, side_effect=write_text_or_fail),
    ):
        exit_code = main(["--output-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Warning: snapshot history not updated: history is read-only" in captured.err
    assert list(tmp_path.glob("ibkr_positions_*.md"))
    assert list(tmp_path.glob("ibkr_positions_*.csv"))
    assert list(tmp_path.glob("ibkr_positions_*.html"))
    assert (tmp_path / "options_tracker_live.csv").exists()
