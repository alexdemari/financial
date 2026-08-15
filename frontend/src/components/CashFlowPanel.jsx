import { Fragment, useMemo, useState } from "react";
import { EmptyState, Panel } from "./Panel";

const PERIOD_OPTIONS = [
  { label: "Last 30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "6m", days: 180 },
  { label: "1y", days: 365 },
  { label: "All", days: null },
];

function filterByPeriod(rows, period) {
  if (period === null) return rows;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - period);
  return rows.filter((row) => new Date(`${row.date}T00:00:00`) >= cutoff);
}

function formatAmount(amount, currency) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
}

function summarize(rows) {
  const flows = rows.filter((row) => row.type === "Deposits/Withdrawals");
  const byCurrency = new Map();
  for (const row of flows) {
    const totals = byCurrency.get(row.currency) || { currency: row.currency, deposited: 0, withdrawn: 0, net: 0 };
    if (row.amount > 0) totals.deposited += row.amount;
    if (row.amount < 0) totals.withdrawn += Math.abs(row.amount);
    totals.net += row.amount;
    byCurrency.set(row.currency, totals);
  }
  return [...byCurrency.values()];
}

export default function CashFlowPanel({ cashFlow }) {
  const { data, loading } = cashFlow;
  const [period, setPeriod] = useState(90);
  const transactions = useMemo(
    () => filterByPeriod(data?.transactions || [], period),
    [data, period],
  );
  const totalsByCurrency = summarize(transactions);

  if (loading) return <Panel title="Fluxo de Caixa"><div className="empty">Loading cash flow…</div></Panel>;
  if (!data?.source?.cash_transactions) {
    return <Panel title="Fluxo de Caixa"><EmptyState command="ibkr-flex-sync" /></Panel>;
  }

  const mismatches = (data.reconciliation || []).filter((row) => !row.reconciles);
  return <Panel title="Fluxo de Caixa">
    <div className="trade-filters">
      <label>Period<select value={period ?? "all"} onChange={(event) => setPeriod(event.target.value === "all" ? null : Number(event.target.value))}>
        {PERIOD_OPTIONS.map((option) => <option value={option.days ?? "all"} key={option.label}>{option.label}</option>)}
      </select></label>
    </div>
    <div className="cash-flow-summary">
      {totalsByCurrency.map((totals) => <Fragment key={totals.currency}>
        <div className="card"><span>Total Aportado ({totals.currency})</span><strong>{formatAmount(totals.deposited, totals.currency)}</strong></div>
        <div className="card"><span>Total Retirado ({totals.currency})</span><strong>{formatAmount(totals.withdrawn, totals.currency)}</strong></div>
        <div className="card"><span>Líquido ({totals.currency})</span><strong className={totals.net >= 0 ? "pos" : "neg"}>{formatAmount(totals.net, totals.currency)}</strong></div>
      </Fragment>)}
    </div>
    {mismatches.length > 0 && <div className="data-warning">Aviso: {mismatches.length} período(s) não reconciliam dentro da tolerância de $1.</div>}
    {transactions.length === 0 ? <div className="empty">No data for selected filters</div> :
      <div className="table-wrap"><table><thead><tr><th>Data</th><th>Tipo</th><th>Valor</th><th>Moeda</th><th>Descrição</th></tr></thead>
        <tbody>{transactions.map((row, index) => <tr key={`${row.date}-${row.type}-${index}`}>
          <td>{row.date}</td><td>{row.type}</td><td className={row.amount >= 0 ? "pos" : "neg"}>{formatAmount(row.amount, row.currency)}</td><td>{row.currency}</td><td>{row.description}</td>
        </tr>)}</tbody></table></div>}
  </Panel>;
}
