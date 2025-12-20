# CLI - Command Line Interface
import argparse
import logging
from pathlib import Path
from typing import List

import pandas as pd

from stock_data_manager.factories.manager_factory import StockDataManagerFactory

BASE_PATH = Path(__file__).parent.parent.resolve()
PROJECT_ROOT = BASE_PATH.parent


class SymbolsLoader:
    """Carrega símbolos de diferentes fontes"""

    @staticmethod
    def from_file(filepath: str) -> List[str]:
        """
        Carrega símbolos de um arquivo

        Args:
            filepath: Caminho do arquivo (txt, csv, ou uma linha por símbolo)

        Returns:
            Lista de símbolos
        """
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

        symbols = []

        # Tenta como CSV primeiro
        if path.suffix.lower() == ".csv":
            try:
                df = pd.read_csv(path)
                # Procura por colunas comuns
                for col in ["symbol", "ticker", "Symbol", "Ticker", "SYMBOL", "TICKER"]:
                    if col in df.columns:
                        symbols = df[col].dropna().str.strip().tolist()
                        break

                # Se não encontrou coluna, usa a primeira
                if not symbols and len(df.columns) > 0:
                    symbols = df.iloc[:, 0].dropna().str.strip().tolist()
            except:
                pass

        # Se não conseguiu ler como CSV ou não é CSV, lê como texto
        if not symbols:
            with open(path, "r", encoding="utf-8") as f:
                symbols = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]

        return symbols

    @staticmethod
    def from_cli(symbols_str: str) -> List[str]:
        """
        Carrega símbolos de string CLI

        Args:
            symbols_str: String com símbolos separados por vírgula ou espaço

        Returns:
            Lista de símbolos
        """
        # Remove espaços extras e separa por vírgula ou espaço
        symbols = symbols_str.replace(",", " ").split()
        return [s.strip() for s in symbols if s.strip()]


class CLI:
    """Interface de linha de comando"""

    def __init__(self):
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Cria o parser de argumentos"""
        parser = argparse.ArgumentParser(
            prog="stock-data-manager",
            description="Gerenciador de dados históricos de ações",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Exemplos de uso:
  # Baixar ações específicas
  %(prog)s -s AAPL MSFT GOOGL

  # Baixar de arquivo
  %(prog)s -f symbols.txt

  # Baixar todos os tickers do arquivo data.json da TradingView
  %(prog)s -a data/data.json -i 1d

  # Especificar diretório de saída
  %(prog)s -s PETR4.SA VALE3.SA -d ./meus_dados

  # Download completo (força re-download)
  %(prog)s -s AAPL --full

  # Usar estratégia de atualização
  %(prog)s -s AAPL --strategy update

Formato do arquivo de símbolos:
  - Texto: um símbolo por linha
  - CSV: coluna com nome 'symbol', 'ticker' ou similar
  - Linhas iniciadas com # são ignoradas
            """,
        )

        # Grupo para especificar símbolos
        symbols_group = parser.add_mutually_exclusive_group(required=True)
        symbols_group.add_argument(
            "-s",
            "--symbols",
            nargs="+",
            metavar="SYMBOL",
            help="Lista de símbolos de ações (ex: AAPL MSFT PETR4.SA)",
        )
        symbols_group.add_argument(
            "-f",
            "--file",
            type=str,
            metavar="FILE",
            help="Arquivo contendo lista de símbolos (txt ou csv)",
        )
        symbols_group.add_argument(
            "-a",
            "--all-tickers",
            type=str,
            metavar="JSON_FILE",
            help="Baixar dados para todos os tickers do arquivo data.json da TradingView",
        )

        # Diretório de saída
        parser.add_argument(
            "-d",
            "--data-dir",
            type=str,
            metavar="DIR",
            help="Diretório onde os arquivos CSV serão salvos (padrão: data/1D)",
        )

        parser.add_argument(
            "-i",
            "--interval",
            type=str,
            default="1d",
            help="Intervalo de tempo dos dados (padrão: 1d). Opções: 1d, 1h, 1w, 1m",
        )

        # Opções adicionais
        parser.add_argument(
            "--full",
            action="store_true",
            help="Força download completo (ignora dados existentes)",
        )

        parser.add_argument(
            "--strategy",
            choices=["append", "update"],
            default="append",
            help="Estratégia de mesclagem de dados (padrão: append)",
        )

        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Modo verboso (mais detalhes no log)",
        )

        parser.add_argument(
            "-q", "--quiet", action="store_true", help="Modo silencioso (apenas erros)"
        )

        return parser

    def parse_args(self, args=None):
        """Parse dos argumentos"""
        return self.parser.parse_args(args)

    def run(self, args=None):
        """Executa o CLI"""
        args = self.parse_args(args)

        # Configura logging
        if args.quiet:
            logging.getLogger().setLevel(logging.ERROR)
        elif args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        try:
            # Carrega símbolos
            if args.symbols:
                symbols = args.symbols
                print(f"📊 Símbolos da linha de comando: {', '.join(symbols)}")
            elif args.all_tickers:
                from stock_data_manager.implementations.trading_view_tickers_reader import TradingViewTickerExtractor
                
                ticker_extractor = TradingViewTickerExtractor(args.all_tickers)
                tickers_df = ticker_extractor.extract_tickers()
                symbols = tickers_df["symbol"].tolist()
                print(f"📁 Carregados {len(symbols)} símbolos do arquivo TradingView: {args.all_tickers}")
            else:
                symbols = SymbolsLoader.from_file(args.file)
                print(f"📁 Carregados {len(symbols)} símbolos de {args.file}")

            if not symbols:
                print("❌ Nenhum símbolo para processar!")
                return 1

            data_output_dir = f"{PROJECT_ROOT}/data/stocks/{args.interval.upper()}"

            # Cria o gerenciador
            if args.strategy == "update":
                manager = StockDataManagerFactory.create_with_update_strategy(
                    data_output_dir
                )
            else:
                manager = StockDataManagerFactory.create_default(data_output_dir)

            # Baixa os dados
            print(
                f"\n{'🔄 Modo: Download completo' if args.full else '⚡ Modo: Incremental'}"
            )
            print(f"📈 Processando {len(symbols)} ativo(s)...\n")
            
            results = manager.download_multiple(symbols, force_full=args.full, interval=args.interval)

            # Exibe resumo
            print("\n" + "=" * 60)
            print("📊 RESUMO DO DOWNLOAD")
            print("=" * 60)

            success_count = 0
            for symbol, data in results.items():
                if data is not None and not data.empty:
                    success_count += 1
                    print(
                        f"✅ {symbol:12} | {len(data):6} registros | "
                        f"{data.index.min().strftime('%Y-%m-%d')} a "
                        f"{data.index.max().strftime('%Y-%m-%d')}"
                    )
                else:
                    print(f"❌ {symbol:12} | Falha no download")

            print("=" * 60)
            print(f"✅ Sucesso: {success_count}/{len(symbols)}")
            print(f"❌ Falhas: {len(symbols) - success_count}/{len(symbols)}")
            print("=" * 60)

            return 0 if success_count > 0 else 1

        except FileNotFoundError as e:
            print(f"❌ Erro: {e}")
            return 1
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            if args.verbose:
                import traceback

                traceback.print_exc()
            return 1
