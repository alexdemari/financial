import pandas as pd
import numpy as np
import glob
import os
from tabulate import tabulate

# Configurações do OptionMaster Pro
PASTA_DADOS = "C:\\Users\\alexa\\Documents\\development\\financial\\data\\stocks\\1D"  # Altere para a pasta onde estão seus 100 CSVs
DIAS_HV = 30
SMA_TREND = 200


def calcular_rsi(df, periods=14):
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def detectar_fvg(df):
    """Detecta o Fair Value Gap mais recente (Ineficiência de Preço)"""
    if len(df) < 3:
        return None
    # FVG de Alta: Low[i] > High[i-2]
    # Usando os últimos 3 candles
    c1, _, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    if c3["Low"] > c1["High"]:
        return f"ALTA em {c1['High']:.2f}-{c3['Low']:.2f}"
    # FVG de Baixa: High[i] < Low[i-2]
    if c3["High"] < c1["Low"]:
        return f"BAIXA em {c3['High']:.2f}-{c1['Low']:.2f}"
    return "Nenhum"


def detectar_order_block(df):
    """Identifica o Order Block de alta (Suporte Institucional) mais próximo"""
    # Simplificação: Candle de baixa com volume 50% acima da média seguido de forte reversão
    vol_mean = df["Volume"].mean()
    for i in range(len(df) - 2, len(df) - 20, -1):
        c = df.iloc[i]
        next_c = df.iloc[i + 1]
        if c["Close"] < c["Open"] and c["Volume"] > vol_mean * 1.5:
            if next_c["Close"] > c["Open"]:  # Reversão forte
                return c["Low"]
    return df["Low"].tail(252).min()  # Fallback para mínima de 52 semanas


def analisar_ativos():
    arquivos = glob.glob(os.path.join(PASTA_DADOS, "*.csv"))
    resultados = []

    print(f"--- Iniciando Scanner OptionMaster Pro em {len(arquivos)} ativos ---")

    for arq in arquivos:
        try:
            ticker = os.path.basename(arq).replace(".csv", "")
            df = pd.read_csv(arq)
            if len(df) < SMA_TREND:
                continue

            # Cálculos Básicos
            preco_atual = df["Close"].iloc[-1]
            retornos = df["Close"].pct_change()
            hv30 = retornos.tail(DIAS_HV).std() * np.sqrt(252) * 100
            sma200 = df["Close"].rolling(window=SMA_TREND).mean().iloc[-1]
            dist_sma = ((preco_atual - sma200) / sma200) * 100
            rsi = calcular_rsi(df).iloc[-1]

            # Cálculos SMC
            ob_suporte = detectar_order_block(df)
            fvg = detectar_fvg(df)

            resultados.append(
                {
                    "Ticker": ticker,
                    "Preço": round(preco_atual, 2),
                    "HV 30d (%)": round(hv30, 2),
                    "Trend (SMA200 %)": round(dist_sma, 2),
                    "RSI": round(rsi, 2),
                    "Suporte OB": round(ob_suporte, 2),
                    "FairValueGap": fvg,
                }
            )
        except Exception as e:
            print(f"Erro ao processar {arq}: {e}")

    df_res = pd.DataFrame(resultados)

    # FILTRO DE ELITE: Tendência de Alta + Volatilidade para prêmio + Não esticado (RSI)
    oportunidades = df_res[
        (df_res["Trend (SMA200 %)"] > 0) & (df_res["RSI"] < 70)
    ].sort_values(by="HV 30d (%)", ascending=False)

    return oportunidades


if __name__ == "__main__":
    ranking = analisar_ativos()
    print("\n--- TOP OPORTUNIDADES PARA JANEIRO/2026 ---")
    print(tabulate(ranking.head(20), headers="keys", tablefmt="psql", showindex=False))

    # Exportar para análise posterior
    ranking.to_csv("oportunidades_detalhadas.csv", index=False)
    print("\nRelatório completo salvo em 'oportunidades_detalhadas.csv'")
