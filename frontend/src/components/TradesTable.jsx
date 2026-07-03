import { useMemo, useState } from "react";
import { Panel } from "./Panel";

const PERIOD_OPTIONS = [
  { label: "Last 30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "6m", days: 180 },
  { label: "1y", days: 365 },
  { label: "All", days: null },
];
const BROKERS = ["all", "IBKR", "BTG-Opções", "BTG-Geral"];
const ASSET_TYPES = ["all", "STK", "OPT", "ETF"];

function filterTrades(trades, { period, broker, assetType }) {
  let filtered = trades;
  if (period !== null) {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - period);
    filtered = filtered.filter((trade) => new Date(`${trade.date}T00:00:00`) >= cutoff);
  }
  if (broker !== "all") {
    filtered = filtered.filter((trade) => trade.broker === broker);
  }
  if (assetType !== "all") {
    filtered = filtered.filter((trade) => trade.asset_type === assetType);
  }
  return filtered;
}

function money(value, currency) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(value);
}

function sourceUpdates(sources) {
  return Object.entries(sources || {})
    .filter(([, source]) => source)
    .map(([name, source]) => `${name.replaceAll("_", " ")}: ${new Date(source.last_updated).toLocaleString()}`)
    .join(" · ");
}

export default function TradesTable({ data }) {
  const [period, setPeriod] = useState(90);
  const [broker, setBroker] = useState("all");
  const [assetType, setAssetType] = useState("all");
  const trades = useMemo(
    () => filterTrades(data?.trades || [], { period, broker, assetType }),
    [data, period, broker, assetType],
  );

  if (!data) return <Panel title="Realized Trades"><div className="empty">Loading trades…</div></Panel>;

  return <>
    <Panel title="Monthly P&L">
      {data.monthly_summary.length === 0 ? <div className="empty">No realized trades yet</div> :
        <div className="trade-summaries">{data.monthly_summary.map((summary) =>
          <article className="trade-summary" key={`${summary.month}-${summary.currency}`}>
            <strong>{summary.month}</strong><span>{summary.currency}</span>
            <dl>
              <div><dt>Gross gains</dt><dd className="pos">{money(summary.gross_gains, summary.currency)}</dd></div>
              <div><dt>Gross losses</dt><dd className="neg">{money(summary.gross_losses, summary.currency)}</dd></div>
              <div><dt>Net P&L</dt><dd className={summary.net_pnl >= 0 ? "pos" : "neg"}>{money(summary.net_pnl, summary.currency)}</dd></div>
              <div><dt>Trades</dt><dd>{summary.trade_count}</dd></div>
            </dl>
          </article>)}</div>}
    </Panel>
    <Panel title="All Trades">
      <div className="trade-filters">
        <label>Period<select value={period ?? "all"} onChange={(event) => setPeriod(event.target.value === "all" ? null : Number(event.target.value))}>
          {PERIOD_OPTIONS.map((option) => <option value={option.days ?? "all"} key={option.label}>{option.label}</option>)}
        </select></label>
        <label>Broker<select value={broker} onChange={(event) => setBroker(event.target.value)}>
          {BROKERS.map((value) => <option value={value} key={value}>{value === "all" ? "All" : value}</option>)}
        </select></label>
        <label>Type<select value={assetType} onChange={(event) => setAssetType(event.target.value)}>
          {ASSET_TYPES.map((value) => <option value={value} key={value}>{value === "all" ? "All" : value}</option>)}
        </select></label>
      </div>
      {trades.length === 0 ? <div className="empty">No data for selected filters</div> :
        <div className="table-wrap"><table><thead><tr>
          <th>Date</th><th>Broker</th><th>Symbol</th><th>Type</th><th>Direction</th>
          <th>Qty</th><th>Price</th><th>Proceeds</th><th>P&amp;L</th>
          <th className="option-detail">Strike</th><th className="option-detail">Expiration</th><th className="option-detail">Strategy</th>
          <th className="mobile-option-details">Option</th>
        </tr></thead><tbody>{trades.map((trade, index) => <tr key={`${trade.broker}-${trade.date}-${trade.symbol}-${index}`}>
          <td>{trade.date}</td><td>{trade.broker}</td><td><strong>{trade.symbol}</strong></td>
          <td><span className={`asset-badge badge-${trade.asset_type.toLowerCase()}`}>{trade.asset_type}</span></td>
          <td>{trade.direction}</td><td>{trade.quantity}</td><td>{money(trade.price, trade.currency)}</td>
          <td>{money(trade.proceeds, trade.currency)}</td>
          <td className={trade.pnl_realized >= 0 ? "pos" : "neg"}>{money(trade.pnl_realized, trade.currency)}</td>
          <td className="option-detail">{trade.strike ?? "—"}</td><td className="option-detail">{trade.expiration ?? "—"}</td>
          <td className="option-detail">{trade.strategy ?? "—"}</td>
          <td className="mobile-option-details">{trade.asset_type === "OPT" ? <details>
            <summary>Details</summary>
            <div>Strike: {trade.strike ?? "—"}</div><div>Expiration: {trade.expiration ?? "—"}</div>
            <div>Strategy: {trade.strategy ?? "—"}</div>
          </details> : "—"}</td>
        </tr>)}</tbody></table></div>}
      <p className="source-updates">Last updated: {sourceUpdates(data.sources) || "never"}</p>
    </Panel>
  </>;
}
