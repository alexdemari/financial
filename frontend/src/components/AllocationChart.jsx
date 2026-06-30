import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { EmptyState, Panel } from "./Panel";

const COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24"];
export default function AllocationChart({ positions }) {
  if (!positions?.length) return <EmptyState command="ibkr-positions" />;
  const grouped = Object.values(positions.reduce((acc, row) => {
    const key = row.asset_type;
    acc[key] = acc[key] || { name: key, value: 0 };
    acc[key].value += Math.abs(row.market_value);
    return acc;
  }, {}));
  return <Panel title="Allocation"><div className="chart"><ResponsiveContainer><PieChart><Pie data={grouped} dataKey="value" innerRadius="55%" outerRadius="80%">
    {grouped.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}
  </Pie><Tooltip formatter={(v) => `$${v.toLocaleString()}`} /><Legend /></PieChart></ResponsiveContainer></div></Panel>;
}
