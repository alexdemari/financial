import { EmptyState, Updated } from "./Panel";

export default function MacroStrip({ macro }) {
  if (!macro || !macro.last_updated) return <EmptyState command="daily" />;
  return <div><div className="macro">{[["Selic", macro.selic], ["USD/BRL", macro.usd_brl], ["S&P 500", macro.sp500], ["Ibovespa", macro.ibov]].map(([key, value]) =>
    <div key={key}><span>{key}</span><strong>{value || "—"}</strong></div>)}</div><Updated value={macro.last_updated} /></div>;
}
