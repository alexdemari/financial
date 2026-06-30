import { EmptyState, Panel } from "./Panel";

export default function OptionsTable({ positions, updated }) {
  const options = (positions || []).filter((row) => row.asset_type === "OPT");
  return <Panel title="Open Options" updated={updated}>
    {!positions?.length ? <EmptyState command="ibkr-positions" /> :
      <div className="table-wrap"><table><thead><tr>
        {["Symbol", "Type", "Strike", "Expiration", "DTE", "P&L", "P&L %", "Risk"].map((x) => <th key={x}>{x}</th>)}
      </tr></thead><tbody>{options.map((row) => <tr key={row.symbol}>
        <td>{row.symbol}</td><td>{row.option_type}</td><td>{row.strike?.toFixed(2)}</td>
        <td>{row.expiration}</td><td>{row.dte}</td><td className={row.unrealized_pnl >= 0 ? "pos" : "neg"}>${row.unrealized_pnl.toFixed(2)}</td>
        <td className={row.return_pct >= 0 ? "pos" : "neg"}>{(row.return_pct * 100).toFixed(1)}%</td>
        <td><span className={`badge ${row.risk_status?.toLowerCase()}`}>{row.risk_status}{row.risk_status === "EXIT" ? " ⚠" : row.risk_status === "WATCH" ? " ~" : ""}</span></td>
      </tr>)}</tbody></table></div>}
  </Panel>;
}
