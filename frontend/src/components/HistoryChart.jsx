import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState, Panel } from "./Panel";

export default function HistoryChart({ entries }) {
  return <Panel title="NLV — Last 90 Days">{!entries?.length ? <EmptyState command="ibkr-positions" /> :
    <div className="history-chart"><ResponsiveContainer><LineChart data={entries}><CartesianGrid stroke="#273449" />
      <XAxis dataKey="date" stroke="#94a3b8" /><YAxis domain={["auto", "auto"]} stroke="#94a3b8" />
      <Tooltip formatter={(v) => `$${v.toLocaleString()}`} /><Line dataKey="nlv" stroke="#38bdf8" dot={false} strokeWidth={2} />
    </LineChart></ResponsiveContainer></div>}</Panel>;
}
