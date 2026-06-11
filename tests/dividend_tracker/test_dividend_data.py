from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from dividend_tracker.dividend_data import (
    DividendCacheError,
    DividendData,
    DividendDistribution,
    calculate_average_annual_dividend,
    fetch_dividend_data,
    normalize_yahoo_ticker,
)


def _dividend_data(
    ticker: str,
    distributions: list[DividendDistribution],
    trailing_annual_dividends: float = 0.0,
) -> DividendData:
    return DividendData(
        ticker=ticker,
        yahoo_ticker=ticker,
        current_price=10.0,
        trailing_annual_dividends=trailing_annual_dividends,
        trailing_dy=0.0,
        distributions=distributions,
        fetched_at=datetime.now(UTC),
    )


def test_normalize_yahoo_ticker_adds_sa_for_br():
    assert normalize_yahoo_ticker("egie3", br=True) == "EGIE3.SA"
    assert normalize_yahoo_ticker("EGIE3.SA", br=True) == "EGIE3.SA"
    assert normalize_yahoo_ticker("schd", br=False) == "SCHD"


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_downloads_and_caches(mock_yf, tmp_path: Path):
    yf_ticker = MagicMock()
    yf_ticker.fast_info.last_price = 50.0
    yf_ticker.dividends = pd.Series(
        [1.0, 1.5],
        index=pd.to_datetime(["2026-01-10", "2026-04-10"]),
    )
    mock_yf.Ticker.return_value = yf_ticker

    result = fetch_dividend_data("EGIE3", br=True, cache_dir=tmp_path)

    assert result.yahoo_ticker == "EGIE3.SA"
    assert result.current_price == 50.0
    assert result.trailing_annual_dividends == 2.5
    assert result.trailing_dy == 0.05
    assert (tmp_path / "EGIE3.csv").exists()
    mock_yf.Ticker.assert_called_once_with("EGIE3.SA")


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_uses_fresh_cache(mock_yf, tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    data = DividendData(
        ticker="SCHD",
        yahoo_ticker="SCHD",
        current_price=80.0,
        trailing_annual_dividends=3.2,
        trailing_dy=0.04,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2026-01-01"), amount=0.8)
        ],
        fetched_at=datetime.now(UTC),
    )
    from dividend_tracker.dividend_data import _write_cache

    _write_cache(cache_path, data)

    result = fetch_dividend_data("SCHD", cache_dir=tmp_path)

    assert result.current_price == 80.0
    mock_yf.Ticker.assert_not_called()


def test_fetch_dividend_data_local_only_requires_cache(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        fetch_dividend_data("SCHD", cache_dir=tmp_path, local_only=True)


def test_fetch_dividend_data_local_only_reports_corrupted_cache(tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    cache_path.write_text(
        "ticker,yahoo_ticker,fetched_at,current_price,trailing_annual_dividends,trailing_dy,date,amount\n"
        "SCHD,SCHD,not-a-date,10,1,0.1,2026-01-01,1\n",
        encoding="utf-8",
    )

    with pytest.raises(DividendCacheError, match="Invalid dividend cache"):
        fetch_dividend_data("SCHD", cache_dir=tmp_path, local_only=True)


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_refreshes_stale_cache(mock_yf, tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    cache_path.write_text(
        "ticker,yahoo_ticker,fetched_at,current_price,trailing_annual_dividends,trailing_dy,date,amount\n"
        "SCHD,SCHD,2026-01-01T00:00:00+00:00,10,1,0.1,2026-01-01,1\n",
        encoding="utf-8",
    )
    old_timestamp = (datetime.now(UTC) - timedelta(days=2)).timestamp()
    cache_path.touch()
    import os

    os.utime(cache_path, (old_timestamp, old_timestamp))

    yf_ticker = MagicMock()
    yf_ticker.fast_info.last_price = 100.0
    yf_ticker.dividends = pd.Series(
        [2.0],
        index=pd.to_datetime(["2026-04-10"]),
    )
    mock_yf.Ticker.return_value = yf_ticker

    result = fetch_dividend_data("SCHD", cache_dir=tmp_path)

    assert result.current_price == 100.0
    mock_yf.Ticker.assert_called_once_with("SCHD")


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_refetches_fresh_corrupted_cache(mock_yf, tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    cache_path.write_text(
        "ticker,yahoo_ticker,fetched_at,current_price,trailing_annual_dividends,trailing_dy,date,amount\n"
        "SCHD,SCHD,not-a-date,10,1,0.1,2026-01-01,1\n",
        encoding="utf-8",
    )

    yf_ticker = MagicMock()
    yf_ticker.fast_info.last_price = 100.0
    yf_ticker.dividends = pd.Series(
        [2.0],
        index=pd.to_datetime(["2026-04-10"]),
    )
    mock_yf.Ticker.return_value = yf_ticker

    result = fetch_dividend_data("SCHD", cache_dir=tmp_path)

    assert result.current_price == 100.0
    mock_yf.Ticker.assert_called_once_with("SCHD")


def test_calculate_average_annual_dividend_correct_mean():
    # Window is [current_year-6, current_year-1] = [2020, 2025].
    # 2026 is the current year and must be excluded.
    distributions = []
    annual_totals = {
        2020: 2.40,
        2021: 2.80,
        2022: 3.20,
        2023: 3.60,
        2024: 4.00,
        2025: 4.40,
    }
    for year, annual_total in annual_totals.items():
        for quarter in range(1, 5):
            distributions.append(
                DividendDistribution(
                    date=pd.Timestamp(f"{year}-{quarter * 3:02d}-10"),
                    amount=annual_total / 4,
                )
            )
    dividend_data = DividendData(
        ticker="PEP",
        yahoo_ticker="PEP",
        current_price=140.0,
        trailing_annual_dividends=4.4,
        trailing_dy=0.031,
        distributions=distributions,
        fetched_at=datetime.now(UTC),
    )

    result = calculate_average_annual_dividend("PEP", dividend_data=dividend_data)

    assert result == pytest.approx(3.40)


def test_calculate_average_annual_dividend_includes_zero_years():
    # Window [2020, 2025]: years 2022 and 2024 have no payments → count as zero.
    # 2026 payment is outside the window and must be excluded.
    dividend_data = DividendData(
        ticker="EGIE3",
        yahoo_ticker="EGIE3.SA",
        current_price=40.0,
        trailing_annual_dividends=3.0,
        trailing_dy=0.075,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2020-03-10"), amount=1.0),
            DividendDistribution(date=pd.Timestamp("2021-03-10"), amount=2.0),
            DividendDistribution(date=pd.Timestamp("2023-03-10"), amount=4.0),
            DividendDistribution(date=pd.Timestamp("2025-03-10"), amount=5.0),
            DividendDistribution(date=pd.Timestamp("2026-03-10"), amount=99.0),
        ],
        fetched_at=datetime.now(UTC),
    )

    result = calculate_average_annual_dividend("EGIE3", dividend_data=dividend_data)

    # {2020:1, 2021:2, 2022:0, 2023:4, 2024:0, 2025:5} → 12/6 = 2.0
    assert result == pytest.approx(2.0)


def test_calculate_average_annual_dividend_raises_on_insufficient_data():
    dividend_data = DividendData(
        ticker="NEW",
        yahoo_ticker="NEW",
        current_price=10.0,
        trailing_annual_dividends=1.0,
        trailing_dy=0.10,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2025-03-10"), amount=1.0),
            DividendDistribution(date=pd.Timestamp("2026-03-10"), amount=1.2),
        ],
        fetched_at=datetime.now(UTC),
    )

    with pytest.raises(ValueError, match="insufficient dividend history"):
        calculate_average_annual_dividend("NEW", dividend_data=dividend_data)


def test_calculate_average_annual_dividend_groups_by_calendar_year():
    # Window [2023, 2025] for years=3. 2026 is excluded (current year).
    # Dec-31 belongs to 2023; Jan-01 belongs to 2024 and 2025 respectively.
    dividend_data = DividendData(
        ticker="CAL",
        yahoo_ticker="CAL",
        current_price=10.0,
        trailing_annual_dividends=1.0,
        trailing_dy=0.10,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2023-12-31"), amount=1.0),
            DividendDistribution(date=pd.Timestamp("2024-01-01"), amount=2.0),
            DividendDistribution(date=pd.Timestamp("2025-01-01"), amount=3.0),
        ],
        fetched_at=datetime.now(UTC),
    )

    result = calculate_average_annual_dividend(
        "CAL", years=3, dividend_data=dividend_data
    )

    # {2023:1, 2024:2, 2025:3} → 6/3 = 2.0
    assert result == pytest.approx(2.0)


def test_average_6y_excludes_current_year():
    """
    O ano corrente incompleto não deve entrar na média.
    """
    current_year = date.today().year
    complete_years = range(current_year - 6, current_year)
    distributions = [
        DividendDistribution(date=pd.Timestamp(f"{year}-06-30"), amount=1.0)
        for year in complete_years
    ]
    distributions.append(
        DividendDistribution(date=pd.Timestamp(f"{current_year}-03-31"), amount=99.0)
    )

    result = calculate_average_annual_dividend(
        "EGIE3",
        dividend_data=_dividend_data("EGIE3", distributions),
    )

    assert result == pytest.approx(1.0)


def test_average_6y_uses_only_complete_years():
    """
    A janela deve conter exatamente `years` anos completos, sem incluir o corrente.
    """
    current_year = date.today().year
    distributions = [
        DividendDistribution(
            date=pd.Timestamp(f"{current_year - offset}-06-30"),
            amount=float(offset),
        )
        for offset in range(1, 8)
    ]
    distributions.append(
        DividendDistribution(date=pd.Timestamp(f"{current_year}-03-31"), amount=99.0)
    )

    result = calculate_average_annual_dividend(
        "BBSE3",
        years=3,
        dividend_data=_dividend_data("BBSE3", distributions),
    )

    assert result == pytest.approx((1.0 + 2.0 + 3.0) / 3)


def test_average_6y_example_sapr4():
    """
    Reproduz o caso SAPR4: o pagamento parcial do ano corrente é excluído.
    """
    current_year = date.today().year
    annual_totals = {
        current_year - 6: 0.103,
        current_year - 5: 0.203,
        current_year - 4: 0.237,
        current_year - 3: 0.373,
        current_year - 2: 0.278,
        current_year - 1: 0.450,
        current_year: 0.113,
    }
    distributions = [
        DividendDistribution(date=pd.Timestamp(f"{year}-06-30"), amount=amount)
        for year, amount in annual_totals.items()
    ]

    result = calculate_average_annual_dividend(
        "SAPR4",
        dividend_data=_dividend_data("SAPR4", distributions),
    )

    assert result == pytest.approx(0.274, abs=0.0001)


def test_average_6y_example_itsa4_growth():
    """
    Documenta que crescimento acelerado pode tornar avg_6y muito menor que TTM.
    """
    current_year = date.today().year
    annual_totals = {
        current_year - 6: 0.12,
        current_year - 5: 0.30,
        current_year - 4: 0.51,
        current_year - 3: 0.52,
        current_year - 2: 0.62,
        current_year - 1: 1.72,
    }
    distributions = [
        DividendDistribution(date=pd.Timestamp(f"{year}-06-30"), amount=amount)
        for year, amount in annual_totals.items()
    ]
    dividend_data = _dividend_data(
        "ITSA4",
        distributions,
        trailing_annual_dividends=1.23,
    )

    average_6y = calculate_average_annual_dividend(
        "ITSA4",
        dividend_data=dividend_data,
    )

    assert average_6y == pytest.approx(sum(annual_totals.values()) / 6)
    assert dividend_data.trailing_annual_dividends / average_6y > 1.9


def test_average_6y_raises_with_less_than_3_complete_years():
    """
    Deve lançar ValueError com menos de 3 anos completos após excluir o corrente.
    """
    current_year = date.today().year
    dividend_data = _dividend_data(
        "NEW",
        [
            DividendDistribution(
                date=pd.Timestamp(f"{current_year - 2}-06-30"),
                amount=1.0,
            ),
            DividendDistribution(
                date=pd.Timestamp(f"{current_year - 1}-06-30"),
                amount=1.2,
            ),
            DividendDistribution(
                date=pd.Timestamp(f"{current_year}-03-31"),
                amount=9.9,
            ),
        ],
    )

    with pytest.raises(ValueError, match="insufficient dividend history"):
        calculate_average_annual_dividend("NEW", dividend_data=dividend_data)
