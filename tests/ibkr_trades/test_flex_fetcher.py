from __future__ import annotations

from pathlib import Path

import pytest

from ibkr_trades import flex_fetcher

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
    monkeypatch.setenv("IBKR_FLEX_QUERY_ID", "test-query")
    monkeypatch.setattr(flex_fetcher.time, "sleep", lambda _: None)


def _error_response(code: str, message: str = "test error") -> bytes:
    return (
        "<FlexStatementResponse>"
        "<Status>Fail</Status>"
        f"<ErrorCode>{code}</ErrorCode>"
        f"<ErrorMessage>{message}</ErrorMessage>"
        "</FlexStatementResponse>"
    ).encode()


def test_fetch_success_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter([_SEND_SUCCESS, _STATEMENT])
    monkeypatch.setattr(flex_fetcher, "_get", lambda _: next(responses))
    output_path = tmp_path / "flex_latest.xml"

    result = flex_fetcher.fetch_flex_query(output_path)

    assert result == output_path
    assert output_path.read_bytes() == _STATEMENT


def test_fetch_retries_on_recoverable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter(
        [
            _SEND_SUCCESS,
            _error_response("1019"),
            _error_response("1019"),
            _STATEMENT,
        ]
    )
    request_count = 0

    def fake_get(_: str) -> bytes:
        nonlocal request_count
        request_count += 1
        return next(responses)

    monkeypatch.setattr(flex_fetcher, "_get", fake_get)

    result = flex_fetcher.fetch_flex_query(tmp_path / "flex_latest.xml")

    assert result is not None
    assert request_count == 4


def test_fetch_returns_none_on_data_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        flex_fetcher, "_get", lambda _: _error_response("1003", "not ready")
    )

    result = flex_fetcher.fetch_flex_query(tmp_path / "flex_latest.xml")

    assert result is None
    assert "Using existing flex_latest.xml" in capsys.readouterr().out


def test_fetch_raises_on_token_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        flex_fetcher, "_get", lambda _: _error_response("1012", "expired")
    )

    with pytest.raises(RuntimeError, match="Flex token expired"):
        flex_fetcher.fetch_flex_query(tmp_path / "flex_latest.xml")


def test_fetch_raises_on_missing_token_before_http_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IBKR_FLEX_TOKEN")

    def unexpected_get(_: str) -> bytes:
        pytest.fail("HTTP must not be called without credentials")

    monkeypatch.setattr(flex_fetcher, "_get", unexpected_get)

    with pytest.raises(EnvironmentError, match="IBKR_FLEX_TOKEN"):
        flex_fetcher.fetch_flex_query(tmp_path / "flex_latest.xml")


def test_fetch_raises_on_missing_query_id_before_http_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IBKR_FLEX_QUERY_ID")

    def unexpected_get(_: str) -> bytes:
        pytest.fail("HTTP must not be called without credentials")

    monkeypatch.setattr(flex_fetcher, "_get", unexpected_get)

    with pytest.raises(EnvironmentError, match="IBKR_FLEX_QUERY_ID"):
        flex_fetcher.fetch_flex_query(tmp_path / "flex_latest.xml")


def test_fetch_writes_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter([_SEND_SUCCESS, _STATEMENT])
    monkeypatch.setattr(flex_fetcher, "_get", lambda _: next(responses))
    output_path = tmp_path / "nested" / "flex_latest.xml"
    original_replace = Path.replace
    replace_calls: list[tuple[Path, Path]] = []

    def tracking_replace(source_path: Path, destination_path: Path) -> Path:
        replace_calls.append((source_path, destination_path))
        return original_replace(source_path, destination_path)

    monkeypatch.setattr(Path, "replace", tracking_replace)

    flex_fetcher.fetch_flex_query(output_path)

    assert replace_calls == [(output_path.with_suffix(".xml.tmp"), output_path)]
    assert output_path.exists()
    assert not output_path.with_suffix(".xml.tmp").exists()


def test_statement_with_nested_status_is_not_treated_as_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    statement_with_status = (
        b"<FlexQueryResponse><FlexStatements>"
        b"<Status>Complete</Status>"
        b"</FlexStatements></FlexQueryResponse>"
    )
    responses = iter([_SEND_SUCCESS, statement_with_status])
    monkeypatch.setattr(flex_fetcher, "_get", lambda _: next(responses))
    output_path = tmp_path / "flex_latest.xml"

    result = flex_fetcher.fetch_flex_query(output_path)

    assert result == output_path
    assert output_path.read_bytes() == statement_with_status


def test_get_sends_required_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request = None

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"response"

    def fake_urlopen(request, timeout):
        nonlocal captured_request
        captured_request = request
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr(flex_fetcher.urllib.request, "urlopen", fake_urlopen)

    assert flex_fetcher._get("https://example.test") == b"response"
    assert captured_request.get_header("User-agent") == "financial/1.0"
