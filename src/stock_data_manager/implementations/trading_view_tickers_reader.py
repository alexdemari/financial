import json
import pandas as pd
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class TickerInfo:
    """
    Data class to hold extracted ticker information.
    Suitable for backtesting: easy to filter, access symbols, sectors.
    """

    symbol: str
    exchange: str
    name: str
    sector: str
    industry: Optional[str] = None  # Optional: lowercase sector from JSON
    price: Optional[float] = None  # Current price from JSON (for quick filters)
    recommendation: Optional[str] = None  # e.g., "Buy", "Neutral"


class TradingViewTickerExtractor:
    """
    Class to read TradingView JSON file and extract tickers into a structured format.
    Designed for backtesting prep: returns Pandas DataFrame for easy querying/filtering.
    """

    def __init__(self, file_path: str):
        """
        Args:
            file_path (str): Path to the JSON file (e.g., 'data.json').
        """
        self.file_path = file_path
        self.data: Optional[pd.DataFrame] = None

    def extract_tickers(self) -> pd.DataFrame:
        """
        Reads the JSON, extracts key fields, and returns a Pandas DataFrame.

        Extracts:
        - symbol: From 's' (e.g., 'A' from 'NYSE:A').
        - exchange: From 's' (e.g., 'NYSE').
        - name: d[1] (full company name).
        - sector: d[23] (formatted sector, e.g., 'Health Technology').
        - industry: d[21] (lowercase sector, e.g., 'health technology').
        - price: d[6] (current price).
        - recommendation: d[24] (e.g., 'Buy').

        Returns:
            pd.DataFrame: Structured data for backtesting (e.g., filter by sector).

        Raises:
            FileNotFoundError: If file not found.
            json.JSONDecodeError: If invalid JSON.
            ValueError: If missing expected fields.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            if "data" not in raw_data or not raw_data["data"]:
                raise ValueError("No 'data' array found in JSON.")

            extracted = []
            for entry in raw_data["data"]:
                s = entry.get("s", "")
                d = entry.get("d", [])

                if len(d) < 25:  # Ensure enough fields
                    continue

                # Parse exchange and symbol
                if ":" in s:
                    exchange, symbol = s.split(":", 1)
                else:
                    exchange, symbol = "Unknown", s

                # Extract fields (indices based on JSON structure)
                name = d[1] if len(d) > 1 else "Unknown"
                industry = d[21] if len(d) > 21 else None  # Lowercase sector
                sector = d[23] if len(d) > 23 else "Unknown"  # Formatted sector
                price = float(d[6]) if len(d) > 6 and d[6] is not None else None
                recommendation = d[24] if len(d) > 24 else None

                extracted.append(
                    TickerInfo(
                        symbol=symbol,
                        exchange=exchange,
                        name=name,
                        sector=sector,
                        industry=industry,
                        price=price,
                        recommendation=recommendation,
                    )
                )

            if not extracted:
                raise ValueError("No valid tickers extracted.")

            # Create DataFrame
            self.data = pd.DataFrame([t.__dict__ for t in extracted])
            self.data = self.data.sort_values(["exchange", "symbol"]).reset_index(
                drop=True
            )

            return self.data
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {self.file_path}")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in {self.file_path}: {str(e)}", e.doc, e.pos
            )
        except Exception as e:
            raise ValueError(f"Error extracting data: {str(e)}")

    def filter_by_sector(self, sector: str) -> pd.DataFrame:
        """
        Filter tickers by sector for targeted backtesting.

        Args:
            sector (str): Sector name (e.g., 'Health Technology').

        Returns:
            pd.DataFrame: Filtered tickers.
        """
        if self.data is None:
            raise ValueError("Run extract_tickers() first.")
        return self.data[self.data["sector"].str.lower() == sector.lower()][
            ["symbol", "name", "sector"]
        ]

    def get_symbols_list(self, exchanges: Optional[List[str]] = None) -> List[str]:
        """
        Get list of symbols (optionally filtered by exchanges) for downloading historical data.

        Args:
            exchanges (Optional[List[str]]): e.g., ['NYSE', 'NASDAQ'].

        Returns:
            List[str]: Symbols ready for backtesting (e.g., yfinance.download(symbols)).
        """
        if self.data is None:
            raise ValueError("Run extract_tickers() first.")

        df_filtered = self.data
        if exchanges:
            df_filtered = df_filtered[df_filtered["exchange"].isin(exchanges)]

        return df_filtered["symbol"].tolist()
