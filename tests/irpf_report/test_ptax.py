from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from irpf_report.ptax import get_ptax


def _write_cache(tmp_path: Path, d: date, rate: float) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / f"{d.isoformat()}.json").write_text(json.dumps({"cotacaoVenda": rate}))


def test_ptax_loads_from_cache_without_network(tmp_path: Path) -> None:
    target = date(2025, 3, 15)
    _write_cache(tmp_path, target, 5.8342)

    with patch("irpf_report.ptax.requests.get") as mock_get:
        result = get_ptax(target, cache_dir=tmp_path)

    assert result == 5.8342
    mock_get.assert_not_called()


def test_ptax_walks_back_on_weekend(tmp_path: Path) -> None:
    # Saturday has no BCB rate; Friday cache should be returned without network I/O
    saturday = date(2025, 3, 15)
    friday = date(2025, 3, 14)
    _write_cache(tmp_path, friday, 5.75)

    # Saturday API returns empty (non-business day); walkback reaches cached Friday
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": []}
    mock_response.raise_for_status.return_value = None

    with patch("irpf_report.ptax.requests.get", return_value=mock_response):
        result = get_ptax(saturday, cache_dir=tmp_path)

    assert result == 5.75


def test_ptax_fetches_from_api_and_caches(tmp_path: Path) -> None:
    target = date(2025, 4, 10)

    mock_response = MagicMock()
    mock_response.json.return_value = {"value": [{"cotacaoVenda": 5.9110}]}
    mock_response.raise_for_status.return_value = None

    with patch("irpf_report.ptax.requests.get", return_value=mock_response):
        result = get_ptax(target, cache_dir=tmp_path)

    assert result == 5.9110
    cache_file = tmp_path / f"{target.isoformat()}.json"
    assert cache_file.exists()
    assert json.loads(cache_file.read_text())["cotacaoVenda"] == 5.9110


def test_ptax_returns_none_when_api_unreachable(tmp_path: Path) -> None:
    target = date(2025, 5, 5)

    with patch("irpf_report.ptax.requests.get", side_effect=Exception("timeout")):
        result = get_ptax(target, max_lookback=0, cache_dir=tmp_path)

    assert result is None
