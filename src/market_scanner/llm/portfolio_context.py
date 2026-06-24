from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_CONCENTRATION_THRESHOLD = 0.25
_MAX_CONTEXT_CHARACTERS = 1_500
_MAX_POSITIONS = 20


def build_portfolio_context(snapshot_path: Path) -> str:
    """Return compact, read-only portfolio context from an IBKR CSV or JSON snapshot."""
    suffix = snapshot_path.suffix.lower()
    if suffix == ".csv":
        positions, metrics = _read_csv_snapshot(snapshot_path)
    elif suffix == ".json":
        positions, metrics = _read_json_snapshot(snapshot_path)
    else:
        raise ValueError("IBKR snapshot must be a CSV or JSON file")

    position_lines = [
        _format_position(position) for position in positions[:_MAX_POSITIONS]
    ]
    if len(positions) > _MAX_POSITIONS:
        position_lines.append(f"... +{len(positions) - _MAX_POSITIONS} more")

    concentration_symbols = sorted(
        {
            _position_symbol(position)
            for position in positions
            if _as_float(position.get("weight")) > _CONCENTRATION_THRESHOLD
        }
    )

    lines = [
        "PORTFOLIO CONTEXT (live, read-only reference):",
        f"Cash available USD: {_format_money(metrics.get('available_cash'))}",
        f"Cash shortfall (short puts worst-case): {_format_money(metrics.get('cash_shortfall'))}",
        f"Net portfolio delta (approx): {_format_signed(metrics.get('net_portfolio_delta'))}",
        "Open positions:",
        *(position_lines or ["none"]),
        "Concentration >25% NLV: "
        + (", ".join(concentration_symbols) if concentration_symbols else "none"),
    ]
    context = "\n".join(lines)
    if len(context) > _MAX_CONTEXT_CHARACTERS:
        context = context[: _MAX_CONTEXT_CHARACTERS - 4].rstrip() + "\n..."
    return context


def _read_csv_snapshot(
    snapshot_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with snapshot_path.open(newline="", encoding="utf-8-sig") as file_handle:
        positions = list(csv.DictReader(file_handle))

    metrics: dict[str, Any] = {}
    if positions:
        first_row = positions[0]
        metrics = {
            "available_cash": first_row.get("available_cash")
            or first_row.get("total_cash"),
            "cash_shortfall": first_row.get("cash_shortfall"),
            "net_portfolio_delta": first_row.get("net_portfolio_delta")
            or first_row.get("net_delta"),
        }
    return positions, metrics


def _read_json_snapshot(
    snapshot_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("IBKR JSON snapshot must contain an object")

    raw_positions = payload.get("positions", [])
    positions = [
        dict(position) for position in raw_positions if isinstance(position, Mapping)
    ]
    summary = payload.get("summary", {})
    risk = payload.get("risk", {})
    summary_mapping = summary if isinstance(summary, Mapping) else {}
    risk_mapping = risk if isinstance(risk, Mapping) else {}
    metrics = {
        "available_cash": summary_mapping.get(
            "total_cash", payload.get("available_cash")
        ),
        "cash_shortfall": risk_mapping.get(
            "cash_shortfall", payload.get("cash_shortfall")
        ),
        "net_portfolio_delta": risk_mapping.get(
            "net_portfolio_delta", payload.get("net_portfolio_delta")
        ),
    }
    return positions, metrics


def _format_position(position: Mapping[str, Any]) -> str:
    symbol = _position_symbol(position)
    asset_type = position.get("type") or position.get("asset_type") or "?"
    quantity = _as_float(position.get("qty") or position.get("quantity"))
    unrealized_pnl = _as_float(position.get("unrealized_pnl"))
    cost_basis = abs(_as_float(position.get("cost_basis")))
    pnl_percent = unrealized_pnl / cost_basis * 100.0 if cost_basis else 0.0
    return f"- {symbol} {asset_type} qty={quantity:g} uPnL={pnl_percent:+.1f}%"


def _position_symbol(position: Mapping[str, Any]) -> str:
    value = position.get("underlying") or position.get("symbol") or "?"
    return str(value)


def _as_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_money(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    return f"${_as_float(value):,.0f}"


def _format_signed(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    return f"{_as_float(value):+.1f}"
