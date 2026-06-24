from io import StringIO

import pytest

from ibkr_positions.reconciler import format_report, reconcile

# ── helpers ──────────────────────────────────────────────────────────────────

TRACKER_HEADER = "Date;Plataform;USD/BRL;Asset;Code;Type;C/V;Due date;Strike;Value (Un.);Qty (Contracts);Costs;Total C/D (Líq.);Delta;IV;POP;Colateral;Close Action;Close Date;Qty (Contracts);Value (Un.);Costs;Result;Size;Close Description\n"
LIVE_HEADER = "entry_date;platform;currency;symbol;underlying;option_type;open_direction;expiration;strike;premium_received;quantity;current_value;unrealized_pnl;delta;iv;dte;collateral;close_action;close_date;close_quantity;close_value;close_costs;result;size;close_description;signal_source\n"


def _tracker(*rows: str) -> StringIO:
    return StringIO(TRACKER_HEADER + "\n".join(rows))


def _live(*rows: str) -> StringIO:
    return StringIO(LIVE_HEADER + "\n".join(rows))


def _tracker_row(
    asset="SMR", type_="PUT", due="17/07/2026", strike="9,00", qty="12", close_date=""
) -> str:
    return f"18/11/2025;IBKR;5.0;{asset};;{type_};V;{due};{strike};1,05;{qty};-0,78;104,22;-0,225;49,19;;0;Compra;{close_date};1;-1,2;-0,77;-16,55;0;test"


def _live_row(
    underlying="SMR",
    option_type="PUT",
    expiration="2026-07-17",
    strike="9,00",
    qty="-12",
) -> str:
    return f"2026-06-23;IBKR;USD;{underlying};{underlying};{option_type};V;{expiration};{strike};330,58;{qty};-339,37;-8,78;;;24;;;;;;;;;;ibkr_live"


# ── tests ─────────────────────────────────────────────────────────────────────


def test_in_sync_when_both_csvs_match():
    result = reconcile(_live(_live_row()), _tracker(_tracker_row()))
    assert result.in_sync is True
    assert result.live_only == []
    assert result.tracker_only == []
    assert result.quantity_mismatch == []


def test_live_only_detected():
    result = reconcile(_live(_live_row()), _tracker(""))
    assert len(result.live_only) == 1
    assert result.live_only[0]["underlying"] == "SMR"
    assert result.in_sync is False


def test_tracker_only_detected():
    result = reconcile(_live(""), _tracker(_tracker_row()))
    assert len(result.tracker_only) == 1
    assert result.tracker_only[0]["underlying"] == "SMR"
    assert result.in_sync is False


def test_closed_tracker_positions_excluded():
    closed_row = _tracker_row(close_date="21/11/2025")
    result = reconcile(_live(""), _tracker(closed_row))
    assert result.tracker_only == []
    assert result.in_sync is True


def test_quantity_mismatch_detected():
    live = _live(_live_row(qty="-6"))
    tracker = _tracker(_tracker_row(qty="12"))
    result = reconcile(live, tracker)
    assert len(result.quantity_mismatch) == 1
    mismatch = result.quantity_mismatch[0]
    assert mismatch["tracker_qty"] == pytest.approx(-12.0)
    assert mismatch["live_qty"] == pytest.approx(-6.0)
    assert result.in_sync is False


def test_multiple_positions_partial_sync():
    live = _live(
        _live_row("SMR", "PUT", "2026-07-17", "9,00", "-12"),
        _live_row("PEP", "PUT", "2026-07-17", "140,00", "-1"),
    )
    tracker = _tracker(_tracker_row("SMR", "PUT", "17/07/2026", "9,00", "12"))
    result = reconcile(live, tracker)
    assert len(result.live_only) == 1
    assert result.live_only[0]["underlying"] == "PEP"
    assert result.tracker_only == []
    assert result.quantity_mismatch == []


def test_reversed_position_detected_as_mismatch():
    """Short in tracker (C/V=V) but long in live must be a qty mismatch, not in-sync."""
    live = _live(_live_row(qty="+12"))  # long in live
    tracker = _tracker(_tracker_row(qty="12"))  # C/V=V → short in tracker
    result = reconcile(live, tracker)
    assert len(result.quantity_mismatch) == 1
    mismatch = result.quantity_mismatch[0]
    assert mismatch["tracker_qty"] == pytest.approx(-12.0)
    assert mismatch["live_qty"] == pytest.approx(12.0)
    assert result.in_sync is False


def test_multiple_tracker_lots_aggregated():
    """Two tracker rows for the same contract (separate lots) are summed before comparison."""
    row_a = _tracker_row(asset="SMR", qty="8")
    row_b = _tracker_row(asset="SMR", qty="4")
    live = _live(_live_row(underlying="SMR", qty="-12"))
    result = reconcile(live, _tracker(row_a, row_b))
    assert result.in_sync is True
    assert result.quantity_mismatch == []


def test_format_report_in_sync():
    result = reconcile(_live(_live_row()), _tracker(_tracker_row()))
    assert "in sync" in format_report(result)


def test_format_report_shows_all_categories():
    live = _live(
        _live_row("AAPL", "CALL", "2026-07-17", "310,00", "-1"),
    )
    tracker = _tracker(
        _tracker_row("FSLY", "PUT", "17/07/2026", "15,00", "5"),
    )
    report = format_report(reconcile(live, tracker))
    assert "LIVE ONLY" in report
    assert "TRACKER ONLY" in report
    assert "AAPL" in report
    assert "FSLY" in report
