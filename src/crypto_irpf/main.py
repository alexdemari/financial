"""CLI to produce an annual Binance crypto IRPF report."""

import argparse
import json
from pathlib import Path

from crypto_irpf.apuracao import apurar_ano
from crypto_irpf.earn import load_earn_records, summarize_earn
from crypto_irpf.report import format_section
from crypto_trades.store import load_trades


def main() -> None:
    """Generate one standalone crypto IRPF markdown report."""
    parser = argparse.ArgumentParser(
        description="Generate a Binance crypto IRPF report"
    )
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--earn", type=Path, required=True)
    parser.add_argument(
        "--cost-basis", type=Path, default=Path("data/crypto/cost_basis.json")
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    content = render_crypto_report(
        arguments.trades, arguments.earn, arguments.cost_basis, arguments.year
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        f"# IRPF {arguments.year + 1} — Criptoativos Binance (ano-base {arguments.year})\n\n{content}",
        encoding="utf-8",
    )


def render_crypto_report(
    trades_path: Path, earn_path: Path, cost_basis_path: Path, year: int
) -> str:
    """Load local canonical data and render the reusable crypto report section."""
    return format_section(
        apurar_ano(load_trades(trades_path), year),
        summarize_earn(load_earn_records(earn_path, year)),
        year,
        load_holdings(cost_basis_path),
    )


def load_holdings(path: Path) -> dict[str, dict[str, float]]:
    """Read T25's cost-basis snapshot for the Bens e Direitos section."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = payload.get("assets", {})
    return {
        asset: {
            "quantity": float(item.get("quantity", 0)),
            "cost_brl": float(item.get("quantity", 0))
            * float(item.get("avg_cost_brl_ptax", 0)),
        }
        for asset, item in assets.items()
    }


if __name__ == "__main__":
    main()
