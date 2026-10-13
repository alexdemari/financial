import { useState } from "react";
import AnalysisView from "./components/AnalysisView";
import InvestmentsView from "./components/InvestmentsView";
import OverviewView from "./components/OverviewView";

const tabs = ["Visão geral", "Investimentos", "Análise"];

// Each view mounts only when its tab is open, so it fetches only its own data.
export default function App() {
  const [tab, setTab] = useState("Visão geral");
  return <main><header className="top"><div><p>LOCAL · READ ONLY</p><h1>Financial Dashboard</h1></div></header>
    <nav>{tabs.map((name) => <button className={tab === name ? "active" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</nav>
    {tab === "Visão geral" && <OverviewView />}
    {tab === "Investimentos" && <InvestmentsView />}
    {tab === "Análise" && <AnalysisView />}
  </main>;
}
