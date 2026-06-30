import { EmptyState, Updated } from "./Panel";

const money = (value) => value == null ? "—" : value.toLocaleString("en-US", { style: "currency", currency: "USD" });
const percent = (value) => value == null ? "—" : `${(value * 100).toFixed(1)}%`;

export default function AccountCards({ account }) {
  if (!account || account.error) return <EmptyState command="ibkr-positions" />;
  const cards = [
    ["NLV", money(account.nlv)], ["Cash", money(account.cash)],
    ["Unrealized P&L", money(account.unrealized_pnl)],
    ["Margin Utilization", percent(account.margin_utilization)],
    ["Net Delta", account.net_delta_approx?.toFixed(1) ?? "—"],
  ];
  return <div><div className="cards">{cards.map(([label, value]) =>
    <article className="card" key={label}><span>{label}</span>
      <strong className={label === "Unrealized P&L" ? (account.unrealized_pnl >= 0 ? "pos" : "neg") : ""}>{value}</strong>
    </article>)}
  </div><Updated value={account.last_updated} /></div>;
}
