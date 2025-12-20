import logging
import sys

from stock_data_manager.cli import CLI
from stock_data_manager.factories.manager_factory import StockDataManagerFactory

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    """Função principal"""
    print("🚀 Iniciando o Gerenciador de Dados de Ações")
    cli = CLI()
    sys.exit(cli.run())


# Exemplo de uso programático
if __name__ == "__main__":
    # Se executado diretamente, pode usar tanto CLI quanto programático
    if len(sys.argv) > 1:
        # Modo CLI
        main()
    else:
        # Modo programático (exemplo)
        print("💡 Modo exemplo programático\n")

        manager = StockDataManagerFactory.create_default()

        symbols = ["AAPL", "PETR4.SA", "VALE3.SA"]

        print("=== Download Incremental ===")
        results = manager.download_multiple(symbols)

        for symbol, data in results.items():
            if data is not None and not data.empty:
                print(f"\n{symbol}:")
                print(f"  Período: {data.index.min()} a {data.index.max()}")
                print(f"  Registros: {len(data)}")
                print(f"  Último fechamento: {data['Close'].iloc[-1]:.2f}")
# from ibapi.client import EClient
# from ibapi.wrapper import EWrapper  

# class IBapi(EWrapper, EClient):
#      def __init__(self):
#          EClient.__init__(self, self) 

# app = IBapi()
# app.connect('127.0.0.1', 7496, 123)
# app.run()

# '''
# #Uncomment this section if unable to connect
# #and to prevent errors on a reconnect
# import time
# time.sleep(2)
# app.disconnect()
# '''
# import pandas as pd
# from ib_insync import *
# import nest_asyncio
# import sys 

# # Necessário para ambientes como Jupyter Notebook
# nest_asyncio.apply()

# # --- Configuração de Parâmetros ---
# TICKER = "AAPL" 
# EXCHANGE = "SMART"
# CURRENCY = "USD"
# PORT = 7496 # 7496 para Live, 7497 para Paper Trading
# CLIENT_ID = 1

# # --- Tratamento de Erro 200 (Essencial) ---

# def handle_error_200(ib: IB, reqId, errorCode, errorString, contract):
#     """Trata erros de requisição, ignorando o comum Erro 200."""
#     if errorCode == 200:
#         if isinstance(contract, Contract):
#             print(f"Aviso: Ignorando Erro 200 para {contract.symbol} @ {contract.strike} | Vencimento: {contract.lastTradeDateOrContractMonth}")
#         else:
#             print(f"Aviso: Ignorando Erro 200 para uma requisição de contrato genérica.")
#     elif errorCode != 200:
#         print(f"❌ ERRO CRÍTICO ({errorCode}): {errorString}. Parando.")
#         ib.disconnect()
#         sys.exit(1)

# # --- Função Principal: Obter Cadeia de Opções Simplificada ---

# def obter_option_chain_simples(ib: IB, ticker: str) -> pd.DataFrame:
#     """Busca um subconjunto da cadeia de opções para validação."""
    
#     # 1. Busca do Contrato Subjacente
#     stock_contract = Stock(ticker, EXCHANGE, CURRENCY)
#     details = ib.reqContractDetails(stock_contract)
    
#     if not details:
#         print(f"❌ Erro: Não foi possível encontrar detalhes para o símbolo '{ticker}'.")
#         return pd.DataFrame()
    
#     underlying_contract = details[0].contract 
    
#     # 2. Obter Parâmetros de Opções (Vencimentos e Strikes)
#     params = ib.reqSecDefOptParams(
#         underlyingSymbol=ticker, 
#         futFopExchange='', 
#         underlyingSecType='STK', 
#         underlyingConId=underlying_contract.conId 
#     )
#     if not params:
#         print(f"❌ Não foram encontrados parâmetros de opções para {ticker}.")
#         return pd.DataFrame()
    
#     opt_param = params[0]
    
#     # 3. FILTRAGEM MAIS SIMPLES: Apenas o primeiro vencimento e 10 strikes
    
#     # Usa o primeiro vencimento listado
#     first_expiration = opt_param.expirations[0] 
    
#     # Usa os primeiros 10 strikes listados
#     selected_strikes = [200.0] #opt_param.strikes[:10] 
#     print(selected_strikes)
#     print(f"Focando no vencimento: {first_expiration} com {len(selected_strikes)} strikes.")

#     # 4. Construir Contratos de Opções (Calls e Puts)
#     all_option_contracts = []
    
#     for strike in selected_strikes:
#         # Call
#         call = Option(
#             symbol=ticker, lastTradeDateOrContractMonth=first_expiration, 
#             strike=strike, right='C', exchange=opt_param.exchange, 
#             currency=CURRENCY
#         )
#         all_option_contracts.append(call)
        
#         # Put
#         put = Option(
#             symbol=ticker, lastTradeDateOrContractMonth=first_expiration, 
#             strike=strike, right='P', exchange=opt_param.exchange, 
#             currency=CURRENCY
#         )
#         all_option_contracts.append(put)

#     # 5. Iteração Síncrona (A solução para o erro anterior)
    
#     final_data = []
    
#     # Anexa o handler de erro para ignorar o Erro 200
#     ib.errorEvent += lambda reqId, errorCode, errorString, contract: handle_error_200(ib, reqId, errorCode, errorString, contract)

#     print(f"\nBuscando detalhes de {len(all_option_contracts)} contratos individualmente...")
    
#     for idx, contract in enumerate(all_option_contracts):
#         # AQUI É O PONTO CHAVE: reqContractDetails com UM ÚNICO contrato
#         details_list = ib.reqContractDetails(contract)
        
#         if details_list:
#             detail = details_list[0].contract
#             final_data.append({
#                 'Symbol': detail.symbol,
#                 'Vencimento': detail.lastTradeDateOrContractMonth,
#                 'Strike': detail.strike,
#                 'Tipo': detail.right, 
#                 'Exchange': detail.exchange,
#             })
            
#     # Remove o handler de erro após a busca
#     ib.errorEvent -= lambda reqId, errorCode, errorString, contract: handle_error_200(ib, reqId, errorCode, errorString, contract)


#     # 6. Criar e retornar o DataFrame
#     df_chain = pd.DataFrame(final_data)
#     if not df_chain.empty:
#         df_chain = df_chain.sort_values(by=['Vencimento', 'Tipo', 'Strike'])
        
#     return df_chain


# # --- 7. Execução Principal ---
# if __name__ == '__main__':
#     ib = IB()

#     try:
#         ib.connect('127.0.0.1', PORT, CLIENT_ID, timeout=10) 
#         print(f"✅ Conectado com sucesso em {ib.client.host}:{ib.client.port}!")
#     except Exception as e:
#         print(f"❌ Erro na conexão: {e}")
#         sys.exit()

#     # Obtém a Cadeia de Opções Simplificada
#     df_options = obter_option_chain_simples(ib, TICKER)
    
#     # Mostra os Resultados
#     if not df_options.empty:
#         print("\n" + "="*50)
#         print(f"✅ SUCESSO! Cadeia de Opções Simplificada OBTIDA para {TICKER}:")
#         print("="*50)
#         print(df_options.to_markdown(index=False))
#         print(f"\nTotal de Opções encontradas: {len(df_options)}")
#     else:
#         print("\n❌ Nenhuma opção válida foi encontrada após a busca.")

#     # Desconecta de forma segura
#     ib.disconnect()
#     print("\nDesconectado da IB.")