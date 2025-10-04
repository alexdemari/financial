import logging
import sys

from stock_data_manager.cli import CLI
from stock_data_manager.factories.manager_factory import StockDataManagerFactory

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    """Função principal"""
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
