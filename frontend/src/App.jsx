import { useState } from "react";
import AccountCards from "./components/AccountCards";
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
import SourcesPanel from "./components/SourcesPanel";
import TradesTable from "./components/TradesTable";
import { useApi } from "./hooks/useApi";

const tabs = ["Visão geral", "Investimentos", "Análise"];

export default function App() {
  const [tab, setTab] = useState("Visão geral");
  const patrimonio = useApi("/api/patrimonio").data;
  const sources = useApi("/api/sources").data;
  const investmentsActive = tab === "Investimentos";
  const analysisActive = tab === "Análise";
  const account = useApi("/api/account", 60_000, investmentsActive).data;
  const positions = useApi("/api/positions", 60_000, investmentsActive).data;
  const risk = useApi("/api/risk", 60_000, investmentsActive).data;
  const history = useApi("/api/history?days=90", 60_000, investmentsActive).data;
  const trades = useApi("/api/trades", 60_000, investmentsActive).data;
  const cashFlow = useApi("/api/cash-flow", 60_000, investmentsActive);
  const macro = useApi("/api/macro", 60_000, analysisActive).data;
  const scanner = useApi("/api/scanner", 60_000, analysisActive).data;
  const scannerReport = useApi("/api/report/scanner", 60_000, analysisActive).data;
  const dividendReport = useApi("/api/report/dividends", 60_000, analysisActive).data;

  return <main><header className="top"><div><p>LOCAL · READ ONLY</p><h1>Financial Dashboard</h1></div></header>
    <nav>{tabs.map((name) => {
      return (
        <button className={tab === name ? "active" : ""} onClick={() => setTab(name)} key={name}>
          {name}
        </button>
      );
    })}</nav>
    {tab === "Visão geral" && <><PatrimonioView data={patrimonio} /><SourcesPanel data={sources} /></>}
    {tab === "Investimentos" && <><AccountCards account={account} /><div className="grid"><AllocationChart positions={positions} /><Panel title="Positions" updated={account?.last_updated}>
      <table><thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Market Value</th><th>P&L</th><th>Weight</th></tr></thead>
      <tbody>{positions?.map((p) => <tr key={p.symbol}><td><strong>{p.symbol}</strong></td><td><span className={`asset-badge badge-${p.asset_type.toLowerCase()}`}>{p.asset_type}</span></td><td>{p.quantity}</td><td>${p.market_value.toFixed(2)}</td><td className={p.unrealized_pnl >= 0 ? "pos" : "neg"}>${p.unrealized_pnl.toFixed(2)}</td><td>{(p.weight * 100).toFixed(1)}%</td></tr>)}</tbody></table></Panel></div>
      <div className="grid"><OptionsTable positions={positions} updated={account?.last_updated} /><RiskAlerts risk={risk} /></div><HistoryChart entries={history} cashFlow={cashFlow.data} /><CashFlowPanel cashFlow={cashFlow} /><TradesTable data={trades} /></>}
    {tab === "Análise" && <><Panel title="Macro"><MacroStrip macro={macro} /></Panel><ScannerTable scanner={scanner} /><ScannerCandidatesTable scanner={scanner} scannerReport={scannerReport} /><DividendDecisionTable dividendReport={dividendReport} /><MarkdownView report={dividendReport} command="dividends-local" title="Dividend Report" /></>}
  </main>;
}
