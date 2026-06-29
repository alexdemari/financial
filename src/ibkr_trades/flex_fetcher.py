from __future__ import annotations

import argparse
import os
import time
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


def fetch_flex_query(
    output_path: Path,
    *,
    max_retries: int = 5,
    retry_wait: float = 5.0,
) -> Path | None:
    """Download the latest IBKR Flex Query XML to ``output_path``."""
    token = _require_env("IBKR_FLEX_TOKEN")
    query_id = _require_env("IBKR_FLEX_QUERY_ID")

    send_url = SEND_URL.format(token=token, query_id=query_id)
    send_response = ET.fromstring(_get(send_url))
    if send_response.findtext("Status") != "Success":
        return _handle_error_response(send_response)

    reference_code = send_response.findtext("ReferenceCode")
    statement_url = send_response.findtext("Url")
    if not reference_code or not statement_url:
        raise RuntimeError(
            "Flex SendRequest succeeded without a ReferenceCode or statement URL"
        )

    get_url = f"{statement_url}?t={token}&q={reference_code}&v=3"
    for attempt in range(1, max_retries + 1):
        # IBKR generates the statement asynchronously, so wait before every retrieval.
        time.sleep(retry_wait)
        content = _get(get_url)
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
        return _handle_error_response(error_response)

    raise RuntimeError("Flex GetStatement: report not ready after all retries")


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


def _handle_error_response(root: ET.Element) -> None:
    error_code = root.findtext("ErrorCode", "")
    error_message = root.findtext("ErrorMessage", "unknown error")
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
    raise RuntimeError(f"Flex Web Service error {error_code}: {error_message}")


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
