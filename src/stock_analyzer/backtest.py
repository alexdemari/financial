import numpy as np
import pandas as pd
import pandas_ta as ta


class TradesMixin:
    def trade(self, df, column, initial_amount):
        trades = []
        position = None
        amount = initial_amount
        stock_quantity = 0

        for i, row in df.iterrows():
            signal = row['Signal']
            price = row[column]

            if signal == 1 and stock_quantity == 0:  # Buy
                stock_quantity = amount / price
                position = {'price': price, 'data': row.name}
                amount = 0
                print(f"Buy in {row.name}: {price:.2f} (used amount: {initial_amount:.2f})")

            elif signal == -1 and stock_quantity > 0:  # Sell
                amount = stock_quantity * price  # Vende tudo
                profit = amount - initial_amount
                trades.append({
                    'input': position['data'],
                    'output': row.name,
                    'input_price': position['price'],
                    'output_price': price,
                    'profit': profit,
                    'return_%': (profit / initial_amount) * 100
                })
                print(f"Sell em {row.name}: {price:.2f} (lucro: {profit:.2f})")
                stock_quantity = 0
                initial_amount = amount

        # Se ainda em posição no final, vende ao último preço
        if stock_quantity > 0:
            last_price = df[column].iloc[-1]
            amount = stock_quantity * last_price
            profit = amount - (initial_amount / stock_quantity * stock_quantity)  # Ajusta
            trades.append({
                'input': position['data'],
                'output' : df.index[-1],
                'input_price': position['price'],
                'output_price': last_price,
                'profit': profit,
                'return_%': (profit / (initial_amount / stock_quantity * stock_quantity)) * 100
            })
            print(f"Sell in {df.index[-1]}: {last_price:.2f} (profit: {profit:.2f})")

        # Resultados
        df_trades = pd.DataFrame(trades)
        if len(trades) > 0:
            total_return = (amount - 10000) / 10000 * 100  # % sobre inicial
            success_rate = (df_trades['profit'] > 0).mean() * 100
        else:
            total_return = 0
            success_rate = 0

        return {
            'initial_amount': 10000,
            'final_amount': float(amount),
            'total_return (%)': round(float(total_return), 2),
            'success_rate (%)': round(float(success_rate), 2),
            'trades_count': len(trades),
            'trades': df_trades
        }


class RSIBacktesting(TradesMixin):
    def _setup(self, df: pd.DataFrame, column: str, period: int):
        df['RSI'] = ta.rsi(df[column], length=period)

        df['Signal'] = 0
        df.loc[df['RSI'] < 30, 'Signal'] = 1  # Buy
        df.loc[df['RSI'] > 70, 'Signal'] = -1  # Sell

    def backtest(self, df, column='Close', period=14, initial_amount=10000):
        self._setup(df, column, period)
        return self.trade(df, column, initial_amount)


class SMABacktesting(TradesMixin):
    def _setup(self, df: pd.DataFrame, column: str, short, long):
        sma_short_key = 'SMA_short'
        sma_long_key = 'SMA_long'
        df[sma_short_key] = ta.sma(df[column], length=short)
        df[sma_long_key] = ta.sma(df[column], length=long)

        signal_key = 'Signal'
        df[signal_key] = 0
        df[signal_key] = np.where((df[sma_short_key] > df[sma_long_key]) & (df[sma_short_key].shift(1) <= df[sma_long_key].shift(1)), 1, df[signal_key])
        df[signal_key] = np.where((df[sma_short_key] < df[sma_long_key]) & (df[sma_short_key].shift(1) >= df[sma_long_key].shift(1)), -1, df[signal_key])

    def analise_sma_crossing(self, df, column='Close', short=20, long=50):
        # Calcula as SMAs usando pandas_ta
        self._setup(df, column, short, long)

        current_signal = df["Signal"].dropna().iloc[-1] if not df["Signal"].dropna().empty else 0
        if current_signal == 1:
            status = "Buy (Cruzamento Altista)"
        elif current_signal == -1:
            status = "Sell (Cruzamento Baixista)"
        else:
            status = "Neutra"

        return status, df

    def backtest(self, df, column='Close',short=20, long=50, capital_inicial=10000):
        self._setup(df, column, short, long)
        return self.trade(df, column, capital_inicial)
