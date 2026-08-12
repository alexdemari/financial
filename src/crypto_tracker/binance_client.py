from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "https://api.binance.com"
REQUEST_TIMEOUT_SECONDS = 10


class BinanceAPIError(RuntimeError):
    """Raised when Binance rejects a request or cannot be reached."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BinanceReadOnlyClient:
    """Minimal Binance Spot client using only the Python standard library."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    def get_spot_balances(self) -> list[dict[str, Any]]:
        """Return non-dust Spot balances with their free and locked amounts."""
        payload = self._request_account()
        balances = payload.get("balances", [])
        if not isinstance(balances, list):
            raise BinanceAPIError("Invalid balances response")

        result = []
        for balance in balances:
            if not isinstance(balance, dict):
                continue
            free = _number(balance.get("free"))
            locked = _number(balance.get("locked"))
            if free + locked > 0.01:
                result.append(
                    {
                        "asset": str(balance.get("asset", "")),
                        "free": free,
                        "locked": locked,
                    }
                )
        return result

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        """Return current USDT prices for the requested symbols in one call."""
        requested_symbols = list(dict.fromkeys(symbols))
        if not requested_symbols:
            return {}

        # Omitting ``symbol`` makes Binance return the complete ticker list.
        # Filtering locally avoids rejecting the entire request when an account
        # contains an asset that has no USDT market.
        payload = self._request("/api/v3/ticker/price", {}, signed=False)
        if not isinstance(payload, list):
            raise BinanceAPIError("Invalid ticker response")

        requested = set(requested_symbols)
        prices: dict[str, float] = {}
        for ticker in payload:
            if not isinstance(ticker, dict):
                continue
            symbol = ticker.get("symbol")
            if symbol in requested and "price" in ticker:
                prices[str(symbol)] = _number(ticker["price"])
        return prices

    def _request_account(self) -> dict[str, Any]:
        timestamp = int(time.time() * 1000)
        query = {"timestamp": timestamp, "recvWindow": 10_000}
        query_string = urllib.parse.urlencode(query)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        query["signature"] = signature
        payload = self._request("/api/v3/account", query, signed=True)
        if not isinstance(payload, dict):
            raise BinanceAPIError("Invalid account response")
        return payload

    def _request(self, endpoint: str, params: dict[str, object], signed: bool) -> Any:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{BASE_URL}{endpoint}?{query}",
            headers={"X-MBX-APIKEY": self.api_key} if signed else {},
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                raw_payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise BinanceAPIError(detail or str(error), error.code) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise BinanceAPIError(str(error)) from error

        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError as error:
            raise BinanceAPIError("Binance returned invalid JSON") from error


def _number(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0
