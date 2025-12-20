import json
import os
import requests
import pandas as pd


class TradingViewDownloader:
    DOWNLOAD_URL = "https://scanner.tradingview.com/america/scan"
    REQUEST_DATA = {
        "columns": [
            "name", "description", "logoid", "update_mode", "type", "typespecs", "close", "pricescale", "minmov",
            "fractional", "minmove2", "currency", "change", "volume", "relative_volume_10d_calc", "market_cap_basic",
            "fundamental_currency_code", "price_earnings_ttm", "earnings_per_share_diluted_ttm",
            "earnings_per_share_diluted_yoy_growth_ttm", "dividends_yield_current", "sector.tr", "market", "sector",
            "AnalystRating", "AnalystRating.tr"
        ],
        "ignore_unknown_fields": False,
        "options": {"lang": "en"},
        "range": [0, 100000],
        "sort": {"sortBy": "name", "sortOrder": "asc", "nullsFirst": False},
        "preset": "all_stocks"
    }

    def __init__(self, download_url: str = DOWNLOAD_URL, request_payload: dict = None):
        self.download_url = download_url
        self.request_data = request_payload or self.REQUEST_DATA

    def download(self, output_file: str) -> pd.DataFrame:
        url = f"{self.download_url}?label-product=markets-screener"
        response = requests.post(url, json=self.request_data)
        response_data = response.json()

        existing_data = {}

        if os.path.exists(output_file):
            with open(output_file, "r") as f:
                existing_data = json.load(f)

        existing_data.update(response_data)

        with open(output_file, "w") as f:
            json.dump(existing_data, f)

        return response_data
