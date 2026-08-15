from __future__ import annotations

import argparse
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SEND_URL = (
    "https://gdcdyn.interactivebrokers.com"
    "/Universal/servlet/FlexStatementService.SendRequest"
    "?t={token}&q={query_id}&v=3"
)
HEADERS = {"User-Agent": "financial/1.0"}

_RECOVERABLE_CODES = {"1001", "1004", "1019"}
_DATA_NOT_READY_CODES = {"1003", "1005", "1006"}
_TOKEN_ERROR_CODES = {"1012", "1013", "1015"}
_CONFIGURATION_ERROR_CODES = {"1025"}


def fetch_flex_query(
    output_path: Path,
    *,
    token_env: str = "IBKR_FLEX_TOKEN",
    query_id_env: str = "IBKR_FLEX_QUERY_ID",
    max_retries: int = 5,
    retry_wait: float = 5.0,
    statement_wait_cap: float | None = None,
    statement_max_total_wait: float | None = None,
) -> Path | None:
    """Download the latest IBKR Flex Query XML to ``output_path``.

    ``token_env``/``query_id_env`` let callers point at a different Flex
    Query (e.g. a Cash Transactions query) sharing the same token.

    By default the GetStatement step polls ``max_retries`` times at a fixed
    ``retry_wait`` interval (unchanged, existing behavior). Passing
    ``statement_max_total_wait`` switches it to exponential backoff instead
    (starting at ``retry_wait``, doubling, capped at ``statement_wait_cap``)
    until that total wall-clock budget is exhausted.
    """
    token = _require_env(token_env)
    query_id = _require_env(query_id_env)

    send_url = SEND_URL.format(token=token, query_id=query_id)
    for attempt in range(1, max_retries + 1):
        try:
            send_response = ET.fromstring(_get(send_url))
        except _TRANSIENT_NETWORK_ERRORS as exc:
            if attempt < max_retries:
                print(
                    f"Flex SendRequest timed out "
                    f"(attempt {attempt}/{max_retries}); retrying..."
                )
                time.sleep(retry_wait)
                continue
            return _handle_transient_network_error(
                exc, output_path, "requesting the Flex statement"
            )

        if send_response.findtext("Status") == "Success":
            break

        error_code = send_response.findtext("ErrorCode", "")
        if error_code in _RECOVERABLE_CODES and attempt < max_retries:
            error_message = send_response.findtext("ErrorMessage", "unknown error")
            print(
                f"Flex SendRequest not ready "
                f"(error {error_code}: {error_message}; "
                f"attempt {attempt}/{max_retries}); retrying..."
            )
            time.sleep(retry_wait)
            continue
        return _handle_error_response(send_response, output_path=output_path)
    else:
        raise RuntimeError("Flex SendRequest: report not ready after all retries")

    reference_code = send_response.findtext("ReferenceCode")
    statement_url = send_response.findtext("Url")
    if not reference_code or not statement_url:
        raise RuntimeError(
            "Flex SendRequest succeeded without a ReferenceCode or statement URL"
        )

    get_url = f"{statement_url}?t={token}&q={reference_code}&v=3"
    if statement_max_total_wait is not None:
        return _poll_get_statement_with_backoff(
            get_url,
            output_path,
            initial_wait=retry_wait,
            wait_cap=statement_wait_cap or retry_wait,
            max_total_wait=statement_max_total_wait,
        )
    return _poll_get_statement_fixed(
        get_url, output_path, max_retries=max_retries, retry_wait=retry_wait
    )


def _poll_get_statement_fixed(
    get_url: str, output_path: Path, *, max_retries: int, retry_wait: float
) -> Path | None:
    for attempt in range(1, max_retries + 1):
        # IBKR generates the statement asynchronously, so wait before every retrieval.
        time.sleep(retry_wait)
        try:
            content = _get(get_url)
        except _TRANSIENT_NETWORK_ERRORS as exc:
            if attempt < max_retries:
                print(
                    f"Flex Web Service timed out "
                    f"(attempt {attempt}/{max_retries}); retrying..."
                )
                continue
            return _handle_transient_network_error(
                exc, output_path, "downloading the Flex statement"
            )

        error_response = _parse_error_response(content)
        if error_response is None:
            _write_atomically(output_path, content)
            print(f"Flex Query downloaded: {output_path} ({len(content):,} bytes)")
            return output_path

        error_code = error_response.findtext("ErrorCode", "")
        if error_code in _RECOVERABLE_CODES and attempt < max_retries:
            print(
                f"Flex report not ready (attempt {attempt}/{max_retries}); retrying..."
            )
            continue
        return _handle_error_response(error_response, output_path=output_path)

    raise RuntimeError("Flex GetStatement: report not ready after all retries")


def _poll_get_statement_with_backoff(
    get_url: str,
    output_path: Path,
    *,
    initial_wait: float,
    wait_cap: float,
    max_total_wait: float,
) -> Path | None:
    elapsed = 0.0
    wait = initial_wait
    while True:
        # IBKR generates the statement asynchronously, so wait before every retrieval.
        time.sleep(wait)
        elapsed += wait
        try:
            content = _get(get_url)
        except _TRANSIENT_NETWORK_ERRORS as exc:
            if elapsed < max_total_wait:
                print(
                    f"Flex Web Service timed out ({elapsed:.0f}s elapsed); retrying..."
                )
                wait = min(wait * 2, wait_cap)
                continue
            return _handle_transient_network_error(
                exc, output_path, "downloading the Flex statement"
            )

        error_response = _parse_error_response(content)
        if error_response is None:
            _write_atomically(output_path, content)
            print(f"Flex Query downloaded: {output_path} ({len(content):,} bytes)")
            return output_path

        error_code = error_response.findtext("ErrorCode", "")
        if error_code in _RECOVERABLE_CODES and elapsed < max_total_wait:
            print(
                f"Flex report not ready (error {error_code}; "
                f"{elapsed:.0f}s/{max_total_wait:.0f}s elapsed); retrying..."
            )
            wait = min(wait * 2, wait_cap)
            continue
        if error_code in _RECOVERABLE_CODES:
            raise RuntimeError(
                f"Flex GetStatement: report not ready after {elapsed:.0f}s "
                f"(max wait {max_total_wait:.0f}s)"
            )
        return _handle_error_response(error_response, output_path=output_path)


_TRANSIENT_NETWORK_ERRORS = (
    TimeoutError,
    urllib.error.URLError,
)


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _require_env(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            "Add it to .env; see .env.example for reference."
        )
    return value


def _parse_error_response(content: bytes) -> ET.Element | None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    root_tag = root.tag.rsplit("}", maxsplit=1)[-1]
    return root if root_tag == "FlexStatementResponse" else None


def _handle_error_response(
    root: ET.Element, *, output_path: Path | None = None
) -> None:
    error_code = root.findtext("ErrorCode", "")
    error_message = root.findtext("ErrorMessage", "unknown error")
    if error_code in _RECOVERABLE_CODES and output_path is not None:
        return _handle_ibkr_recoverable_error(error_code, error_message, output_path)
    if error_code in _DATA_NOT_READY_CODES:
        print(
            f"Flex data not yet available for today "
            f"(error {error_code}: {error_message}).\n"
            "Activity statements update after market close (~22:00 ET).\n"
            "Using existing flex_latest.xml if present."
        )
        return None
    if error_code in _TOKEN_ERROR_CODES:
        raise RuntimeError(
            f"Flex token error ({error_code}: {error_message}).\n"
            "Flex token expired. Renew at: "
            "Settings → Account Settings → Flex Web Service"
        )
    if error_code in _CONFIGURATION_ERROR_CODES:
        raise RuntimeError(
            f"Flex configuration error ({error_code}: {error_message}).\n"
            "Stop retrying for now; IBKR is rejecting the Flex Web Service "
            "request. Review IBKR_FLEX_TOKEN and IBKR_FLEX_QUERY_ID in .env, "
            "then verify the token at: "
            "Client Portal → Settings → Account Settings → Flex Web Service "
            "and the query id at: Performance & Reports → Flex Queries."
        )
    raise RuntimeError(f"Flex Web Service error {error_code}: {error_message}")


def _handle_ibkr_recoverable_error(
    error_code: str, error_message: str, output_path: Path
) -> Path | None:
    if output_path.exists():
        print(
            f"Flex Web Service temporarily unavailable "
            f"(error {error_code}: {error_message}).\n"
            f"Using existing {output_path}."
        )
        return None
    raise RuntimeError(
        f"Flex Web Service temporarily unavailable "
        f"(error {error_code}: {error_message}).\n"
        f"No existing {output_path} found to reuse."
    )


def _handle_transient_network_error(
    exc: BaseException, output_path: Path, action_description: str
) -> Path | None:
    if output_path.exists():
        print(
            f"Flex Web Service unavailable while {action_description}: {exc}.\n"
            f"Using existing {output_path}."
        )
        return None
    raise RuntimeError(
        f"Flex Web Service unavailable while {action_description}: {exc}.\n"
        f"No existing {output_path} found to reuse."
    ) from exc


def _write_atomically(output_path: Path, content: bytes) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the latest IBKR Flex Query XML."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/ibkr/flex_latest.xml"),
        help="destination XML path (default: data/ibkr/flex_latest.xml)",
    )
    arguments = parser.parse_args()
    result = fetch_flex_query(arguments.output)
    if result is None:
        print("Skipped; using existing file.")


if __name__ == "__main__":
    main()
