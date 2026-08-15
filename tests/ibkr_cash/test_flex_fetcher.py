from __future__ import annotations

from pathlib import Path

import pytest

from ibkr_cash import flex_fetcher
from ibkr_trades import flex_fetcher as trades_flex_fetcher

_SEND_SUCCESS = b"""\
<FlexStatementResponse>
  <Status>Success</Status>
  <ReferenceCode>reference-123</ReferenceCode>
  <Url>https://example.test/GetStatement</Url>
</FlexStatementResponse>
"""
_STATEMENT = b"<FlexQueryResponse><FlexStatements /></FlexQueryResponse>"


@pytest.fixture(autouse=True)
def flex_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "test-token")
    monkeypatch.setenv("IBKR_FLEX_QUERY_ID_CASH", "test-cash-query")
    monkeypatch.setattr(trades_flex_fetcher.time, "sleep", lambda _: None)


def test_fetch_cash_flex_query_uses_cash_query_id_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_urls: list[str] = []
    responses = iter([_SEND_SUCCESS, _STATEMENT])

    def fake_get(url: str) -> bytes:
        seen_urls.append(url)
        return next(responses)

    monkeypatch.setattr(trades_flex_fetcher, "_get", fake_get)
    output_path = tmp_path / "flex_cash_latest.xml"

    result = flex_fetcher.fetch_cash_flex_query(output_path)

    assert result == output_path
    assert output_path.read_bytes() == _STATEMENT
    assert "q=test-cash-query" in seen_urls[0]


def _error_response(
    code: str, message: str = "statement generation in progress"
) -> bytes:
    return (
        "<FlexStatementResponse>"
        "<Status>Fail</Status>"
        f"<ErrorCode>{code}</ErrorCode>"
        f"<ErrorMessage>{message}</ErrorMessage>"
        "</FlexStatementResponse>"
    ).encode()


def test_fetch_cash_flex_query_survives_repeated_1019_within_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter(
        [_SEND_SUCCESS, _error_response("1019"), _error_response("1019"), _STATEMENT]
    )
    monkeypatch.setattr(trades_flex_fetcher, "_get", lambda _: next(responses))

    result = flex_fetcher.fetch_cash_flex_query(tmp_path / "flex_cash_latest.xml")

    assert result is not None
    assert result.read_bytes() == _STATEMENT


def test_fetch_cash_flex_query_gives_up_after_max_total_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Always-recoverable: every GetStatement poll reports "not ready".
    monkeypatch.setattr(
        trades_flex_fetcher,
        "_get",
        lambda url: _SEND_SUCCESS if "SendRequest" in url else _error_response("1019"),
    )

    with pytest.raises(RuntimeError, match="not ready after"):
        flex_fetcher.fetch_cash_flex_query(
            tmp_path / "flex_cash_latest.xml",
            initial_wait=5.0,
            wait_cap=30.0,
            max_total_wait=90.0,
        )


def test_fetch_cash_flex_query_missing_env_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IBKR_FLEX_QUERY_ID_CASH", raising=False)

    with pytest.raises(EnvironmentError):
        flex_fetcher.fetch_cash_flex_query(tmp_path / "flex_cash_latest.xml")
