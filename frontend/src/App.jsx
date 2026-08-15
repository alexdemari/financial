import { useState } from "react";
import AccountCards from "./components/AccountCards";
import AttentionBanner from "./components/AttentionBanner";
import AllocationChart from "./components/AllocationChart";
import CashFlowPanel from "./components/CashFlowPanel";
import DividendDecisionTable from "./components/DividendDecisionTable";
import HistoryChart from "./components/HistoryChart";
import MacroStrip from "./components/MacroStrip";
import MarkdownView from "./components/MarkdownView";
import OptionsTable from "./components/OptionsTable";
import PatrimonioView from "./components/PatrimonioView";
import { Panel } from "./components/Panel";
import RiskAlerts from "./components/RiskAlerts";
import ScannerCandidatesTable from "./components/ScannerCandidatesTable";
import ScannerTable from "./components/ScannerTable";
import TradesTable from "./components/TradesTable";
import { useApi } from "./hooks/useApi";

const tabs = ["Patrimônio", "Dashboard", "Portfolio", "History", "Scanner", "Dividends", "Trades"];

function isStale(isoString) {
  if (!isoString) return false;
  return (new Date() - new Date(isoString)) > 25 * 60 * 60 * 1000;
}

export default function App() {
  const [tab, setTab] = useState("Patrimônio");
  const patrimonio = useApi("/api/patrimonio").data;
  const account = useApi("/api/account").data;
  const positions = useApi("/api/positions").data;
  const risk = useApi("/api/risk").data;
  const macro = useApi("/api/macro").data;
  const history = useApi("/api/history?days=90").data;
  const scanner = useApi("/api/scanner").data;
  const scannerReport = useApi("/api/report/scanner").data;
  const dividendReport = useApi("/api/report/dividends").data;
  const trades = useApi("/api/trades").data;
  const recentHistory = useApi("/api/history?days=2").data;
  const cashFlow = useApi("/api/cash-flow");

  function tabDotColor(name) {
    if (name === "Scanner" && isStale(scanner?.last_updated)) return "amber";
    if (name === "Dividends" && isStale(dividendReport?.last_updated)) return "amber";
    if (name === "Patrimônio" && Object.values(patrimonio?.allocation ?? {}).some((a) => a.severity === "outside")) return "red";
    return null;
  }

  return <main><header className="top"><div><p>LOCAL · READ ONLY</p><h1>Financial Dashboard</h1></div></header>
    <AttentionBanner risk={risk} scanner={scanner} positions={positions} recentHistory={recentHistory} />
    <nav>{tabs.map((name) => {
      const dotColor = tabDotColor(name);
      return (
        <button className={tab === name ? "active" : ""} onClick={() => setTab(name)} key={name}>
          <span style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
            {name}
            {dotColor && (
              <span style={{
                position: "absolute",
                top: "-4px",
                right: "-10px",
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: dotColor === "amber" ? "#f59e0b" : "#ef4444",
                flexShrink: 0,
              }} />
            )}
          </span>
        </button>
      );
    })}</nav>
    {tab === "Patrimônio" && <PatrimonioView data={patrimonio} />}
    {tab === "Dashboard" && <><AccountCards account={account} /><Panel title="Macro"><MacroStrip macro={macro} /></Panel>
      <div className="grid"><OptionsTable positions={positions} updated={account?.last_updated} /><RiskAlerts risk={risk} /></div><ScannerTable scanner={scanner} /></>}
    {tab === "Portfolio" && <div className="grid"><AllocationChart positions={positions} /><Panel title="Positions" updated={account?.last_updated}>
      <table><thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Market Value</th><th>P&L</th><th>Weight</th></tr></thead>
      <tbody>{positions?.map((p) => <tr key={p.symbol}><td><strong>{p.symbol}</strong></td><td><span className={`asset-badge badge-${p.asset_type.toLowerCase()}`}>{p.asset_type}</span></td><td>{p.quantity}</td><td>${p.market_value.toFixed(2)}</td><td className={p.unrealized_pnl >= 0 ? "pos" : "neg"}>${p.unrealized_pnl.toFixed(2)}</td><td>{(p.weight * 100).toFixed(1)}%</td></tr>)}</tbody></table></Panel></div>}
    {tab === "History" && <><HistoryChart entries={history} cashFlow={cashFlow.data} /><CashFlowPanel cashFlow={cashFlow} /></>}
    {tab === "Scanner" && <ScannerCandidatesTable scanner={scanner} scannerReport={scannerReport} />}
    {tab === "Dividends" && <><DividendDecisionTable dividendReport={dividendReport} /><MarkdownView report={dividendReport} command="dividends-local" title="Dividend Report" /></>}
    {tab === "Trades" && <TradesTable data={trades} />}
  </main>;
}
