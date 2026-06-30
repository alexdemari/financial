from __future__ import annotations

from datetime import date

from web.readers import history_jsonl, ibkr_csv, macro_report, scan_csv, tracker_csv
from web.readers.markdown import render_markdown


CSV_HEADER = (
    "symbol,type,qty,market_value,cost_basis,unrealized_pnl,weight,underlying,"
    "option_type,strike,expiration,available_cash,cash_shortfall,net_portfolio_delta\n"
)


def test_account_snapshot_returns_none_without_history(tmp_path, monkeypatch):
    monkeypatch.setattr(history_jsonl, "HISTORY_PATH", tmp_path / "missing.jsonl")
    assert history_jsonl.read_account_snapshot() is None


def test_account_snapshot_reads_history_fields(tmp_path, monkeypatch):
    path = tmp_path / "history.jsonl"
    path.write_text(
        '{"date":"2026-06-29","nlv":400,"cash":100,"invested":300,'
        '"unrealized_pnl":50,"margin_utilization":0.2,"net_delta_approx":2}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(history_jsonl, "HISTORY_PATH", path)
    snapshot = history_jsonl.read_account_snapshot()
    assert snapshot is not None
    assert snapshot.nlv == 400
    assert snapshot.cash == 100
    assert snapshot.margin_utilization == 0.2


def test_latest_ibkr_csv_returns_newest_dated_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ibkr_csv, "REPORTS_DIR", tmp_path)
    older = tmp_path / "ibkr_positions_2026-06-01.csv"
    newer = tmp_path / "ibkr_positions_2026-06-30.csv"
    older.touch()
    newer.touch()
    assert ibkr_csv.latest_ibkr_csv() == newer


def test_read_positions_computes_dte_and_exit_status(tmp_path, monkeypatch):
    monkeypatch.setattr(ibkr_csv, "REPORTS_DIR", tmp_path)
    (tmp_path / "ibkr_positions_2026-06-29.csv").write_text(
        CSV_HEADER
        + "AAPL OPT,OPT,-1,-20,30,10,0.05,AAPL,PUT,100,2026-07-04,100,0,-10\n",
        encoding="utf-8",
    )
    position = ibkr_csv.read_positions(today=date(2026, 6, 29))[0]
    assert position.dte == 5
    assert position.risk_status == "EXIT"


def test_option_risk_status_thresholds():
    assert ibkr_csv.option_risk_status(7) == "EXIT"
    assert ibkr_csv.option_risk_status(14) == "WATCH"
    assert ibkr_csv.option_risk_status(15) == "HOLD"


def test_history_sorted_and_limited(tmp_path, monkeypatch):
    path = tmp_path / "history.jsonl"
    path.write_text(
        "\n".join(
            f'{{"date":"2026-01-0{day}","nlv":{day}}}' for day in [5, 1, 4, 2, 3]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(history_jsonl, "HISTORY_PATH", path)
    assert read_dates(history_jsonl.read_history(days=3)) == [
        "2026-01-03",
        "2026-01-04",
        "2026-01-05",
    ]


def test_positions_skip_missing_identity_and_tolerate_bad_expiration(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ibkr_csv, "REPORTS_DIR", tmp_path)
    (tmp_path / "ibkr_positions_2026-06-29.csv").write_text(
        CSV_HEADER
        + ",STK,1,20,10,10,0.2,,,,,100,0,2\n"
        + "AAPL OPT,OPT,-1,-20,30,10,0.05,AAPL,PUT,100,bad-date,100,0,-10\n",
        encoding="utf-8",
    )
    positions = ibkr_csv.read_positions(today=date(2026, 6, 29))
    assert len(positions) == 1
    assert positions[0].dte is None


def test_tracker_reader_uses_semicolon_delimiter(tmp_path, monkeypatch):
    path = tmp_path / "options_tracker.csv"
    path.write_text(
        "symbol;underlying;option_type;close_date\n"
        "AAPL;AAPL;PUT;\nMSFT;MSFT;CALL;2026-06-01\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tracker_csv, "TRACKER_PATH", path)
    assert tracker_csv.read_open_legs()["rows"] == [
        {
            "symbol": "AAPL",
            "underlying": "AAPL",
            "option_type": "PUT",
            "close_date": "",
        }
    ]


def test_macro_reader_parses_named_markdown_table(tmp_path, monkeypatch):
    path = tmp_path / "report.md"
    path.write_text(
        "| Indicator | Value |\n|---|---|\n"
        "| Selic (meta) | 14.25% |\n| USD/BRL (PTAX) | 5.10 |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(macro_report, "REPORT_PATH", path)
    result = macro_report.read_macro()
    assert result["selic"] == "14.25%"
    assert result["usd_brl"] == "5.10"
    assert result["sp500"] is None


def test_render_markdown_missing(tmp_path):
    assert render_markdown(tmp_path / "missing.md") == {
        "html": "",
        "last_updated": None,
        "exists": False,
    }


def test_scan_reader_returns_ranked_candidates(tmp_path, monkeypatch):
    path = tmp_path / "scan.csv"
    path.write_text(
        "symbol,action_bucket,consistency_score\n"
        "LOW,candidate,2\nHIGH,candidate,8\nNO,avoid,10\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(scan_csv, "SCAN_PATH", path)
    assert [row["symbol"] for row in scan_csv.read_scan()["rows"]] == ["HIGH", "LOW"]


def read_dates(entries):
    return [entry["date"] for entry in entries]
