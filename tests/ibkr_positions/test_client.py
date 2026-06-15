from unittest.mock import MagicMock, patch

import pytest
import requests

from ibkr_positions.client import IBKRClient, IBKRConnectionError
import fixtures  # noqa: E402 — loaded via conftest sys.path insert

MOCK_ACCOUNTS_RESPONSE = fixtures.MOCK_ACCOUNTS_RESPONSE
MOCK_LEDGER_RESPONSE = fixtures.MOCK_LEDGER_RESPONSE
MOCK_POSITIONS_RESPONSE = fixtures.MOCK_POSITIONS_RESPONSE
MOCK_SUMMARY_RESPONSE = fixtures.MOCK_SUMMARY_RESPONSE


def _make_response(json_data):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


def _ordered_get(*responses):
    """Return a side_effect that cycles through responses in call order."""
    call_count = [0]

    def side_effect(url, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return responses[idx] if idx < len(responses) else _make_response({})

    return side_effect


def _patched_client(mock_session_class, *responses) -> IBKRClient:
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_session.get.side_effect = _ordered_get(*responses)
    return IBKRClient()


@patch("ibkr_positions.client.requests.Session")
def test_get_portfolio_success(mock_session_class):
    client = _patched_client(
        mock_session_class,
        _make_response(MOCK_ACCOUNTS_RESPONSE),
        _make_response(MOCK_SUMMARY_RESPONSE),
        _make_response(MOCK_LEDGER_RESPONSE),
        _make_response(MOCK_POSITIONS_RESPONSE),
    )

    portfolio = client.get_portfolio()

    assert portfolio.account_id == "U1234567"
    assert portfolio.summary.net_liquidation == 50000.0
    assert portfolio.summary.total_cash == 10000.0
    assert len(portfolio.positions) == 2


@patch("ibkr_positions.client.requests.Session")
def test_get_portfolio_parses_stock_position(mock_session_class):
    client = _patched_client(
        mock_session_class,
        _make_response(MOCK_ACCOUNTS_RESPONSE),
        _make_response(MOCK_SUMMARY_RESPONSE),
        _make_response(MOCK_LEDGER_RESPONSE),
        _make_response(MOCK_POSITIONS_RESPONSE),
    )

    portfolio = client.get_portfolio()
    stock = next(p for p in portfolio.positions if p.asset_type == "STK")

    assert stock.symbol == "AAPL"
    assert stock.quantity == 100.0
    assert stock.market_value == 18000.0
    assert stock.unrealized_pnl == 3000.0
    assert stock.expiration is None
    assert stock.option_type is None
    assert stock.delta is None


@patch("ibkr_positions.client.requests.Session")
def test_get_portfolio_parses_option_position(mock_session_class):
    client = _patched_client(
        mock_session_class,
        _make_response(MOCK_ACCOUNTS_RESPONSE),
        _make_response(MOCK_SUMMARY_RESPONSE),
        _make_response(MOCK_LEDGER_RESPONSE),
        _make_response(MOCK_POSITIONS_RESPONSE),
    )

    portfolio = client.get_portfolio()
    opt = next(p for p in portfolio.positions if p.asset_type == "OPT")

    assert opt.option_type == "PUT"
    assert opt.strike == 140.0
    assert opt.expiration == "2027-01-15"
    assert opt.underlying == "PEP"
    assert opt.delta == -0.32
    assert opt.underlying_price == 152.0


@patch("ibkr_positions.client.requests.Session")
def test_client_portal_not_running_raises_clear_error(mock_session_class):
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_session.get.side_effect = requests.exceptions.ConnectionError("refused")

    with pytest.raises(IBKRConnectionError) as exc_info:
        IBKRClient().get_portfolio()

    error_msg = str(exc_info.value)
    assert "IBKR Client Portal is not running" in error_msg
    assert "https://localhost:5000" in error_msg


@patch("ibkr_positions.client.requests.Session")
def test_partial_response_missing_optional_fields(mock_session_class):
    minimal_position = [
        {
            "contractDesc": "MSFT",
            "ticker": "MSFT",
            "position": 50.0,
            "mktValue": 10000.0,
            "assetClass": "STK",
            # avgCost, unrealizedPnl, expiry, delta all absent
        }
    ]
    client = _patched_client(
        mock_session_class,
        _make_response(MOCK_ACCOUNTS_RESPONSE),
        _make_response(MOCK_SUMMARY_RESPONSE),
        _make_response(MOCK_LEDGER_RESPONSE),
        _make_response(minimal_position),
    )

    portfolio = client.get_portfolio()
    assert len(portfolio.positions) == 1
    pos = portfolio.positions[0]
    assert pos.symbol == "MSFT"
    assert pos.cost_basis == 0.0
    assert pos.expiration is None
    assert pos.delta is None


@patch("ibkr_positions.client.requests.Session")
def test_http_error_raises_ibkr_connection_error(mock_session_class):
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    err_response = MagicMock()
    err_response.status_code = 401
    mock_session.get.side_effect = requests.exceptions.HTTPError(
        "401 Unauthorized", response=err_response
    )

    with pytest.raises(IBKRConnectionError) as exc_info:
        IBKRClient().get_portfolio()

    assert "HTTP error" in str(exc_info.value)
