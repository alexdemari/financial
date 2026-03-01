import numpy as np
import pandas as pd
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)


class TradesMixin:
    def trade(self, df, column, initial_amount):
        trades = []
        position = None
        cash = initial_amount
        stock_quantity = 0
        portfolio_value = initial_amount

        for date, row in df.iterrows():
            signal = row["Signal"]
            price = row[column]

            if signal == 1 and stock_quantity == 0:  # Buy
                stock_quantity = cash / price
                position = {"price": price, "date": date}
                cash = 0
                logger.info(f"Buy {date}: {price:.2f}")

            elif signal == -1 and stock_quantity > 0:  # Sell
                revenue = stock_quantity * price
                profit = revenue - initial_amount
                trades.append(
                    {
                        "entry_date": position["date"],
                        "exit_date": date,
                        "entry_price": position["price"],
                        "exit_price": price,
                        "profit": profit,
                        "return_%": (profit / initial_amount) * 100
                        if initial_amount > 0
                        else 0,
                    }
                )
                logger.info(f"Sell {date}: {price:.2f} (P&L: {profit:.2f})")
                cash = revenue
                stock_quantity = 0

            # Atualizar valor portfolio
            portfolio_value = cash + (
                stock_quantity * price if stock_quantity > 0 else 0
            )

        # Finalizar posição aberta
        if stock_quantity > 0:
            last_price = df[column].iloc[-1]
            revenue = stock_quantity * last_price
            profit = revenue - initial_amount
            trades.append(
                {
                    "entry_date": position["date"],
                    "exit_date": df.index[-1],
                    "entry_price": position["price"],
                    "exit_price": last_price,
                    "profit": profit,
                    "return_%": (profit / initial_amount) * 100
                    if initial_amount > 0
                    else 0,
                }
            )
            portfolio_value = revenue

        # Calcular métricas
        df_trades = pd.DataFrame(trades)
        total_return = (
            (portfolio_value - initial_amount) / initial_amount * 100
            if initial_amount > 0
            else 0
        )
        success_rate = (
            (df_trades["profit"] > 0).mean() * 100 if len(df_trades) > 0 else 0
        )

        return {
            "initial_amount": initial_amount,
            "final_amount": float(portfolio_value),
            "total_return_%": round(float(total_return), 2),
            "success_rate_%": round(float(success_rate), 2),
            "trades_count": len(trades),
            "trades": df_trades,
        }


class RSIBacktesting(TradesMixin):
    def _setup(
        self,
        df: pd.DataFrame,
        column: str,
        period: int,
        lower_limit: int,
        upper_limit: int,
    ):
        df["RSI"] = ta.rsi(df[column], length=period)

        df["Signal"] = 0
        df.loc[df["RSI"] < lower_limit, "Signal"] = 1  # Buy
        df.loc[df["RSI"] > upper_limit, "Signal"] = -1  # Sell

    def backtest(
        self,
        df,
        column="Close",
        period=14,
        initial_amount=10000,
        lower_limit=30,
        upper_limit=70,
    ):
        self._setup(df, column, period, lower_limit, upper_limit)
        return self.trade(df, column, initial_amount)


class SMAPairBacktesting(TradesMixin):
    def _setup(self, df: pd.DataFrame, column: str, short, long):
        sma_short_key = "SMA_short"
        sma_long_key = "SMA_long"
        df[sma_short_key] = ta.sma(df[column], length=short)
        df[sma_long_key] = ta.sma(df[column], length=long)

        signal_key = "Signal"
        df[signal_key] = 0
        df[signal_key] = np.where(
            (df[sma_short_key] > df[sma_long_key])
            & (df[sma_short_key].shift(1) <= df[sma_long_key].shift(1)),
            1,
            df[signal_key],
        )
        df[signal_key] = np.where(
            (df[sma_short_key] < df[sma_long_key])
            & (df[sma_short_key].shift(1) >= df[sma_long_key].shift(1)),
            -1,
            df[signal_key],
        )

    def analise_sma_crossing(self, df, column="Close", short=20, long=50):
        # Calcula as SMAs usando pandas_ta
        self._setup(df, column, short, long)

        current_signal = (
            df["Signal"].dropna().iloc[-1] if not df["Signal"].dropna().empty else 0
        )
        if current_signal == 1:
            status = "Buy (Cruzamento Altista)"
        elif current_signal == -1:
            status = "Sell (Cruzamento Baixista)"
        else:
            status = "Neutra"

        return status, df

    def backtest(self, df, column="Close", short=20, long=50, capital_inicial=10000):
        self._setup(df, column, short, long)
        return self.trade(df, column, capital_inicial)


class CCIBacktesting(TradesMixin):
    """
    Mean Reversion CCI Backtesting (long-only, no SL/TP).
    - Buy: CCI < LowTh (oversold).
    - Sell: CCI > HighTh (reversion).
    - Fixed risk: 500$ per trade (~5% allocation).
    - Vectorized returns; loop for trade details.
    """

    def _setup(
        self,
        df: pd.DataFrame,
        close_column: str,
        cci_period: int,
        low_th: float,
        high_th: float,
        initial_capital: float,
        commission_rate: float = 0.001,
    ):
        # Compute CCI (requires HLC)
        df["CCI"] = ta.cci(df["High"], df["Low"], df[close_column], length=cci_period)

        # Signals: 1=Buy if CCI < low_th, -1=Sell if CCI > high_th
        df["Signal"] = 0
        df.loc[df["CCI"] < low_th, "Signal"] = 1
        df.loc[df["CCI"] > high_th, "Signal"] = -1

        # Daily returns
        df["Market_Return"] = df[close_column].pct_change()

        # Position (ffill, long-only)
        df["Position"] = df["Signal"].replace(0, method="ffill").fillna(0).clip(0, 1)

        # Strategy returns (lagged, with commissions)
        df["Strategy_Return"] = df["Position"].shift(1) * df["Market_Return"]
        df.loc[df["Signal"].abs() == 1, "Strategy_Return"] -= commission_rate

        # Cumulative
        df["Cumulative_Strategy"] = (
            1 + df["Strategy_Return"].fillna(0)
        ).cumprod() * initial_capital

    def backtest(
        self,
        df: pd.DataFrame,
        close_column: str = "Close",
        cci_period: int = 14,
        low_th: float = -100,
        high_th: float = 100,
        initial_capital: float = 10000,
        risked_money: float = 500,
        commission_rate: float = 0.001,
    ) -> dict:
        """
        Runs CCI Mean Reversion backtest.

        Args:
            df: OHLC DataFrame.
            close_column: Price column.
            cci_period: CCI length.
            low_th: Buy threshold.
            high_th: Sell threshold.
            initial_capital: Starting capital.
            risked_money: Risk per trade (used for sizing: risked_money / initial_capital).
            commission_rate: Fee.

        Returns:
            Dict: Results with metrics, trades, equity curve.
        """
        # Setup
        self._setup(
            df,
            close_column,
            cci_period,
            low_th,
            high_th,
            initial_capital,
            commission_rate,
        )

        # Position size fraction
        size_fraction = risked_money / initial_capital  # ~5%

        # Trade simulation (loop for details; vectorized returns above)
        trades = self.trade(df, close_column, initial_capital)  # Uses TradesMixin

        # Advanced Metrics (from vectorized)
        strategy_returns = df["Strategy_Return"].dropna()
        total_return = (
            (df["Cumulative_Strategy"].iloc[-1] - initial_capital)
            / initial_capital
            * 100
        )
        sharpe = (
            strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
            if strategy_returns.std() != 0
            else 0
        )
        rolling_max = df["Cumulative_Strategy"].expanding().max()
        drawdown = (df["Cumulative_Strategy"] - rolling_max) / rolling_max * 100
        max_dd = drawdown.min()
        calmar = total_return / abs(max_dd) if max_dd != 0 else 0

        # Enhance trades with size
        for trade in trades["trades"]:
            trade["size_fraction"] = size_fraction

        return {
            "initial_capital": initial_capital,
            "final_capital": df["Cumulative_Strategy"].iloc[-1],
            "total_return_%": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown_%": max_dd,
            "calmar_ratio": calmar,
            "num_trades": len(trades["trades"]),
            "win_rate_%": trades["success_rate (%)"],
            "trades": trades["trades"],
            "equity_curve": df["Cumulative_Strategy"],
        }
