import { useState } from "react";
import AccountCards from "./components/AccountCards";
import AllocationChart from "./components/AllocationChart";
import HistoryChart from "./components/HistoryChart";
import MacroStrip from "./components/MacroStrip";
import MarkdownView from "./components/MarkdownView";
import OptionsTable from "./components/OptionsTable";
import { Panel } from "./components/Panel";
import RiskAlerts from "./components/RiskAlerts";
import ScannerTable from "./components/ScannerTable";
import { useApi } from "./hooks/useApi";

const tabs = ["Dashboard", "Portfolio", "History", "Scanner", "Dividends"];
export default function App() {
  const [tab, setTab] = useState("Dashboard");
  const account = useApi("/api/account").data;
  const positions = useApi("/api/positions").data;
  const risk = useApi("/api/risk").data;
  const macro = useApi("/api/macro").data;
  const history = useApi("/api/history?days=90").data;
  const scanner = useApi("/api/scanner").data;
  const scannerReport = useApi("/api/report/scanner").data;
  const dividendReport = useApi("/api/report/dividends").data;
  return <main><header className="top"><div><p>LOCAL · READ ONLY</p><h1>Financial Dashboard</h1></div>
    <nav>{tabs.map((name) => <button className={tab === name ? "active" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</nav></header>
    {tab === "Dashboard" && <><AccountCards account={account} /><Panel title="Macro"><MacroStrip macro={macro} /></Panel>
      <div className="grid"><OptionsTable positions={positions} updated={account?.last_updated} /><RiskAlerts risk={risk} /></div><ScannerTable scanner={scanner} /></>}
    {tab === "Portfolio" && <div className="grid"><AllocationChart positions={positions} /><Panel title="Positions" updated={account?.last_updated}>
      <table><thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Market Value</th><th>P&L</th><th>Weight</th></tr></thead>
      <tbody>{positions?.map((p) => <tr key={p.symbol}><td><strong>{p.symbol}</strong></td><td><span className={`asset-badge badge-${p.asset_type.toLowerCase()}`}>{p.asset_type}</span></td><td>{p.quantity}</td><td>${p.market_value.toFixed(2)}</td><td className={p.unrealized_pnl >= 0 ? "pos" : "neg"}>${p.unrealized_pnl.toFixed(2)}</td><td>{(p.weight * 100).toFixed(1)}%</td></tr>)}</tbody></table></Panel></div>}
    {tab === "History" && <HistoryChart entries={history} />}
    {tab === "Scanner" && <MarkdownView report={scannerReport} command="daily" title="Scanner Report" />}
    {tab === "Dividends" && <MarkdownView report={dividendReport} command="dividends-local" title="Dividend Report" />}
  </main>;
}
