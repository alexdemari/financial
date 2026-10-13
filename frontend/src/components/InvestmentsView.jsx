import { useApi } from "../hooks/useApi";
import AccountCards from "./AccountCards";
import AllocationChart from "./AllocationChart";
import CashFlowPanel from "./CashFlowPanel";
import HistoryChart from "./HistoryChart";
import OptionsTable from "./OptionsTable";
import { Panel } from "./Panel";
import RiskAlerts from "./RiskAlerts";
import TradesTable from "./TradesTable";

export default function InvestmentsView() {
  const account = useApi("/api/account").data;
  const positions = useApi("/api/positions").data;
  const risk = useApi("/api/risk").data;
  const history = useApi("/api/history?days=90").data;
  const trades = useApi("/api/trades").data;
  const cashFlow = useApi("/api/cash-flow");
  return <><AccountCards account={account} /><div className="grid"><AllocationChart positions={positions} /><Panel title="Positions" updated={account?.last_updated}>
    <table><thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Market Value</th><th>P&L</th><th>Weight</th></tr></thead>
    <tbody>{positions?.map((p) => <tr key={p.symbol}><td><strong>{p.symbol}</strong></td><td><span className={`asset-badge badge-${p.asset_type.toLowerCase()}`}>{p.asset_type}</span></td><td>{p.quantity}</td><td>${p.market_value.toFixed(2)}</td><td className={p.unrealized_pnl >= 0 ? "pos" : "neg"}>${p.unrealized_pnl.toFixed(2)}</td><td>{(p.weight * 100).toFixed(1)}%</td></tr>)}</tbody></table></Panel></div>
    <div className="grid"><OptionsTable positions={positions} updated={account?.last_updated} /><RiskAlerts risk={risk} /></div><HistoryChart entries={history} cashFlow={cashFlow.data} /><CashFlowPanel cashFlow={cashFlow} /><TradesTable data={trades} /></>;
}
