"""
Analisador de dados de ações (refatorado).
Responsabilidade única: Orquestrar análise de dados.
"""

import logging
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from stock_analyzer.config import IndicatorConfig
from stock_analyzer.signals import (
    AnalyzerSignalAdapter,
    LuxSignalGenerator,
    SignalGenerator,
    SMCSignalGenerator,
)
from stock_data_manager.factories.manager_factory import StockDataManagerFactory

logger = logging.getLogger(__name__)
SignalModel = Literal["rsi-sma", "lux", "smc"]


class StockDataAnalyzer:
    """
    Orquestrador de análise.
    Delega cálculos para especialistas.
    """

    def __init__(
        self, config: IndicatorConfig = None, signal_model: SignalModel = "rsi-sma"
    ):
        self.config = config or IndicatorConfig()
        self.signal_model = signal_model
        self.signal_generator = self._create_signal_generator(signal_model)
        logger.info(f"StockDataAnalyzer inicializado com config: {self.config}")

    def _create_signal_generator(
        self, signal_model: SignalModel
    ) -> AnalyzerSignalAdapter:
        if signal_model == "rsi-sma":
            return SignalGenerator(self.config)
        if signal_model == "lux":
            return LuxSignalGenerator()
        if signal_model == "smc":
            return SMCSignalGenerator()
        raise ValueError(f"Unsupported signal model: {signal_model}")

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Any:
        """
        Gera sinal para o candle atual.

        Args:
            symbol: Ticker
            df: DataFrame com dados OHLC

        Returns:
            SignalResult ou None se inválido
        """
        return self.signal_generator.generate_current_signal(symbol, df)

    def generate_historical_signals(
        self, symbol: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Gera histórico completo de sinais.

        Args:
            symbol: Ticker
            df: DataFrame com dados OHLC

        Returns:
            DataFrame com sinais históricos
        """
        return self.signal_generator.generate_historical_signals(symbol, df)

    @staticmethod
    def retrieve_data(
        symbol: str, data_dir: str | Path, interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Recupera dados mais recentes.

        Args:
            symbol: Ticker
            interval: '1d', '1w', '1m'

        Returns:
            DataFrame com dados limpos
        """
        try:
            interval_data_dir = Path(data_dir) / interval.upper()
            sdm = StockDataManagerFactory.create_with_update_strategy(
                data_dir=str(interval_data_dir)
            )

            df = sdm.download_and_save(symbol, interval=interval)

            if df.empty:
                logger.warning(f"{symbol}: Nenhum dado recuperado")
                return df

            df.dropna(inplace=True)
            logger.info(f"{symbol}: {len(df)} linhas recuperadas")
            return df

        except Exception as e:
            logger.error(f"Erro ao recuperar dados para {symbol}: {e}", exc_info=True)
            raise

    @staticmethod
    def load_local_data(
        symbol: str, data_dir: str | Path, interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Carrega dados locais existentes sem atualizar nem baixar.

        Args:
            symbol: Ticker
            interval: '1d', '1w', '1m'

        Returns:
            DataFrame com dados locais limpos
        """
        interval_data_dir = Path(data_dir) / interval.upper()
        manager = StockDataManagerFactory.create_default(
            data_dir=str(interval_data_dir)
        )
        df = manager.get_data(symbol)

        if df is None:
            filepath = interval_data_dir / f"{symbol}.csv"
            raise FileNotFoundError(f"Local CSV not found: {filepath}")

        if df.empty:
            logger.warning(f"{symbol}: Arquivo local vazio")
            return df

        df = df.copy()
        df.dropna(inplace=True)
        logger.info(f"{symbol}: {len(df)} linhas carregadas localmente")
        return df
