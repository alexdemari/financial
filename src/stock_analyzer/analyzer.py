"""
Analisador de dados de ações (refatorado).
Responsabilidade única: Orquestrar análise de dados.
"""

import logging
from typing import Optional

import pandas as pd

from stock_analyzer.signals import SignalGenerator, SignalResult
from stock_analyzer.config import IndicatorConfig
from stock_data_manager.factories.manager_factory import StockDataManagerFactory

logger = logging.getLogger(__name__)


class StockDataAnalyzer:
    """
    Orquestrador de análise.
    Delega cálculos para especialistas.
    """

    def __init__(self, config: IndicatorConfig = None):
        self.config = config or IndicatorConfig()
        self.signal_generator = SignalGenerator(self.config)
        logger.info(f"StockDataAnalyzer inicializado com config: {self.config}")

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[SignalResult]:
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
    def retrieve_data(symbol: str, data_dir: str, interval: str = "1d") -> pd.DataFrame:
        """
        Recupera dados mais recentes.

        Args:
            symbol: Ticker
            interval: '1d', '1w', '1m'

        Returns:
            DataFrame com dados limpos
        """
        try:
            sdm = StockDataManagerFactory().create_with_update_strategy(
                data_dir=f"{data_dir}\{interval.upper()}"
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
