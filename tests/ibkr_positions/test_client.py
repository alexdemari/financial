from unittest.mock import MagicMock, patch

import pytest

from ibkr_positions.client import IBKRClient, IBKRConnectionError
import fixtures  # noqa: E402 — loaded via conftest sys.path insert


def _make_ib_mock(
    accounts=None,
    account_values=None,
    portfolio_items=None,
) -> MagicMock:
    ib = MagicMock()
    ib.managedAccounts.return_value = ["U1234567"] if accounts is None else accounts
    ib.accountValues.return_value = (
        fixtures.MOCK_ACCOUNT_VALUES if account_values is None else account_values
    )
    ib.portfolio.return_value = (
        fixtures.MOCK_PORTFOLIO_ITEMS if portfolio_items is None else portfolio_items
    )
    return ib


def _patched_client(mock_ib_class, ib_mock: MagicMock) -> IBKRClient:
    mock_ib_class.return_value = ib_mock
    return IBKRClient()


@patch("ibkr_positions.client.IB")
def test_get_portfolio_success(mock_ib_class):
    ib_mock = _make_ib_mock()
    client = _patched_client(mock_ib_class, ib_mock)

    portfolio = client.get_portfolio()

    assert portfolio.account_id == "U1234567"
    assert portfolio.summary.net_liquidation == 50000.0
    assert portfolio.summary.total_cash == 10000.0
    assert len(portfolio.positions) == 2


@patch("ibkr_positions.client.IB")
def test_get_portfolio_parses_stock_position(mock_ib_class):
    client = _patched_client(mock_ib_class, _make_ib_mock())

    portfolio = client.get_portfolio()
    stock = next(p for p in portfolio.positions if p.asset_type == "STK")

    assert stock.symbol == "AAPL"
    assert stock.quantity == 100.0
    assert stock.market_value == 18000.0
    assert stock.unrealized_pnl == 3000.0
    assert stock.expiration is None
    assert stock.option_type is None
    assert stock.delta is None


@patch("ibkr_positions.client.IB")
def test_get_portfolio_parses_option_position(mock_ib_class):
    client = _patched_client(mock_ib_class, _make_ib_mock())

    portfolio = client.get_portfolio()
    opt = next(p for p in portfolio.positions if p.asset_type == "OPT")

    assert opt.option_type == "PUT"
    assert opt.strike == 140.0
    assert opt.expiration == "2027-01-15"
    assert opt.underlying == "PEP"
    assert opt.delta is None
    assert opt.underlying_price is None


@patch("ibkr_positions.client.IB")
def test_gateway_not_running_raises_clear_error(mock_ib_class):
    ib_mock = MagicMock()
    mock_ib_class.return_value = ib_mock
    ib_mock.connect.side_effect = ConnectionRefusedError("refused")

    with pytest.raises(IBKRConnectionError) as exc_info:
        IBKRClient().get_portfolio()

    error_msg = str(exc_info.value)
    assert "IB Gateway is not running" in error_msg
    assert "7496" in error_msg


@patch("ibkr_positions.client.IB")
def test_no_accounts_raises_error(mock_ib_class):
    ib_mock = _make_ib_mock(accounts=[])
    client = _patched_client(mock_ib_class, ib_mock)

    with pytest.raises(IBKRConnectionError, match="No accounts"):
        client.get_portfolio()


@patch("ibkr_positions.client.IB")
def test_disconnect_called_even_on_error(mock_ib_class):
    ib_mock = _make_ib_mock(accounts=[])
    mock_ib_class.return_value = ib_mock

    with pytest.raises(IBKRConnectionError):
        IBKRClient().get_portfolio()

    ib_mock.disconnect.assert_called_once()


@patch("ibkr_positions.client.IB")
def test_cash_balances_parsed_by_currency(mock_ib_class):
    client = _patched_client(mock_ib_class, _make_ib_mock())

    portfolio = client.get_portfolio()
    currencies = {cb.currency for cb in portfolio.cash}

    assert "USD" in currencies
    assert "BRL" in currencies


@patch("ibkr_positions.client.IB")
def test_unparseable_position_skipped(mock_ib_class):
    bad_item = MagicMock()
    bad_item.account = "U1234567"
    bad_item.contract.secType = "STK"
    bad_item.contract.symbol = "BAD"
    bad_item.position = "not_a_number"  # will cause float() to fail

    ib_mock = _make_ib_mock(
        portfolio_items=[bad_item] + list(fixtures.MOCK_PORTFOLIO_ITEMS)
    )
    client = _patched_client(mock_ib_class, ib_mock)

    portfolio = client.get_portfolio()
    # bad item skipped, 2 good positions remain
    assert len(portfolio.positions) == 2
