from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from dividend_tracker.config import DividendAssetConfig
from dividend_tracker.price_ceiling import PriceCeilingResult
from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.enums import Signal


DividendDecision = Literal["BUY", "WATCH", "WAIT", "OVERPRICED"]
TechnicalSignal = Literal["BUY", "WATCH", "WAIT", "NEUTRAL"]


class ConvictionLevel(Enum):
    NONE = "none"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True)
class TechnicalSignalResult:
    signal: TechnicalSignal
    model: str
    event_type: str
    days_since_event: int | None
    interpretation: str


@dataclass(frozen=True)
class AssetDecision:
    asset: DividendAssetConfig
    price_ceiling: PriceCeilingResult
    technical_signal: TechnicalSignalResult
    decision: DividendDecision
    description: str
    conviction: ConvictionLevel = ConvictionLevel.NONE
    confirmation_signal: TechnicalSignalResult | None = None

    @property
    def primary_signal(self) -> TechnicalSignalResult:
        return self.technical_signal


def evaluate_asset(
    asset_config: DividendAssetConfig,
    price_ceiling_result: PriceCeilingResult,
    technical_signal: TechnicalSignalResult,
    confirmation_signal: TechnicalSignalResult | None = None,
) -> AssetDecision:
    if not price_ceiling_result.is_below_or_equal_ceiling:
        decision: DividendDecision = "OVERPRICED"
        description = "Fora do preco teto"
        conviction = ConvictionLevel.NONE
    elif technical_signal.signal == "BUY":
        decision = "BUY"
        if confirmation_signal is not None and confirmation_signal.signal == "BUY":
            conviction = ConvictionLevel.HIGH
            description = "Comprar agora - alta conviccao"
        else:
            conviction = ConvictionLevel.NORMAL
            description = "Comprar agora"
    elif technical_signal.signal == "WATCH":
        decision = "WATCH"
        description = "Monitorar - entrada proxima"
        conviction = ConvictionLevel.NORMAL
    else:
        decision = "WAIT"
        description = "Preco ok, aguardar sinal tecnico"
        conviction = ConvictionLevel.NONE

    return AssetDecision(
        asset=asset_config,
        price_ceiling=price_ceiling_result,
        technical_signal=technical_signal,
        decision=decision,
        description=description,
        conviction=conviction,
        confirmation_signal=confirmation_signal,
    )


def get_technical_signal(
    asset_config: DividendAssetConfig,
    data_dir: str | Path = "data/stocks",
    local_only: bool = True,
    model: str | None = None,
) -> TechnicalSignalResult:
    technical_model = model or asset_config.technical_models.primary
    interval = asset_config.timeframe.lower()
    analyzer = StockDataAnalyzer(signal_model=technical_model)
    symbol = asset_config.yahoo_ticker
    if local_only:
        ohlc_df = analyzer.load_local_data(symbol, data_dir=data_dir, interval=interval)
    else:
        # retrieve_data downloads via yfinance when local cache is missing/stale.
        # Use --local-only to skip all network calls.
        ohlc_df = analyzer.retrieve_data(symbol, data_dir=data_dir, interval=interval)

    current_signal = analyzer.generate_signal(symbol, ohlc_df)
    historical_signals = analyzer.generate_historical_signals(symbol, ohlc_df)
    signal = _map_current_signal(current_signal)
    event_type, days_since_event = _recent_event(historical_signals)
    interpretation = (
        analyzer.signal_generator.interpret(current_signal)
        if current_signal is not None
        else "No current technical signal available."
    )
    if signal == "NEUTRAL" and event_type == "BUY" and days_since_event == 0:
        signal = "WATCH"

    return TechnicalSignalResult(
        signal=signal,
        model=technical_model,
        event_type=event_type,
        days_since_event=days_since_event,
        interpretation=interpretation,
    )


def get_asset_technical_signals(
    asset_config: DividendAssetConfig,
    data_dir: str | Path = "data/stocks",
    local_only: bool = True,
) -> tuple[TechnicalSignalResult, TechnicalSignalResult | None]:
    primary_signal = get_technical_signal(
        asset_config,
        data_dir=data_dir,
        local_only=local_only,
        model=asset_config.technical_models.primary,
    )
    confirmation_model = asset_config.technical_models.confirmation
    if confirmation_model is None:
        return primary_signal, None
    confirmation_signal = get_technical_signal(
        asset_config,
        data_dir=data_dir,
        local_only=local_only,
        model=confirmation_model,
    )
    return primary_signal, confirmation_signal


def _map_current_signal(current_signal: Any) -> TechnicalSignal:
    if current_signal is None:
        return "NEUTRAL"
    combined_signal = getattr(current_signal, "combined_signal", Signal.HOLD)
    if combined_signal == Signal.BUY or combined_signal == 1:
        return "BUY"
    if combined_signal == Signal.HOLD or combined_signal == 0:
        return "WAIT"
    return "WAIT"


def _recent_event(historical_signals: pd.DataFrame) -> tuple[str, int | None]:
    if historical_signals.empty or "combined_signal" not in historical_signals.columns:
        return "NONE", None

    event_rows = historical_signals[
        historical_signals["combined_signal"].isin([Signal.BUY, Signal.SELL, 1, -1])
    ]
    if event_rows.empty:
        return "NONE", None

    last_event_index = event_rows.index[-1]
    last_event = event_rows.iloc[-1]
    combined_signal = last_event["combined_signal"]
    event_type = (
        "BUY" if combined_signal == Signal.BUY or combined_signal == 1 else "SELL"
    )
    try:
        days_since_event = int(
            len(historical_signals)
            - 1
            - historical_signals.index.get_loc(last_event_index)
        )
    except TypeError:
        days_since_event = None
    return event_type, days_since_event
