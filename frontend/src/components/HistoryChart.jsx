import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "../hooks/useApi";
import { EmptyState, Panel } from "./Panel";

function mergeContributed(entries, cumulativeContributed) {
  const usdContributed = (cumulativeContributed || []).filter((row) => row.currency === "USD");
  const contributedByDate = Object.fromEntries(usdContributed.map((row) => [row.date, row.contributed]));
  const firstDate = entries[0]?.date;
  let lastContributed = usdContributed
    .filter((row) => row.date <= firstDate)
    .at(-1)?.contributed;
  return entries.map((entry) => {
    if (contributedByDate[entry.date] != null) lastContributed = contributedByDate[entry.date];
    return { ...entry, contributed: lastContributed };
  });
}

function buildNormalizedData(entries, ibovHistory, cumulativeContributed) {
  // Build lookup maps keyed by date string
  const nlvByDate = Object.fromEntries(entries.map((e) => [e.date, e.nlv]));
  const ibovByDate = Object.fromEntries(ibovHistory.map((e) => [e.date, e.value]));

  // Find first date present in both series
  const nlvDates = entries.map((e) => e.date).sort();
  const baseDate = nlvDates.find((d) => ibovByDate[d] != null);
  if (!baseDate) return null;

  const nlvBase = nlvByDate[baseDate];
  const ibovBase = ibovByDate[baseDate];
  if (!nlvBase || !ibovBase) return null;

  // Merge all dates from entries (primary axis); attach ibov where available
  const mergedEntries = mergeContributed(entries, cumulativeContributed);
  return mergedEntries.map((e) => ({
    date: e.date,
    nlv_normalized: ((e.nlv / nlvBase) * 100),
    ibov_normalized: ibovByDate[e.date] != null ? ((ibovByDate[e.date] / ibovBase) * 100) : undefined,
    contributed_normalized: e.contributed != null ? ((e.contributed / nlvBase) * 100) : undefined,
  }));
}

export default function HistoryChart({ entries, cashFlow }) {
  const macro = useApi("/api/macro").data;
  const [showNlv, setShowNlv] = useState(true);
  const [showIbov, setShowIbov] = useState(true);

  const ibovHistory = macro?.ibov_history;
  const hasIbov = Array.isArray(ibovHistory) && ibovHistory.length > 0;

  if (!hasIbov) {
    // Original rendering — unchanged
    return (
      <Panel title="NLV — Last 90 Days">
        {!entries?.length ? <EmptyState command="ibkr-positions" /> :
          <div className="history-chart"><ResponsiveContainer><LineChart data={mergeContributed(entries, cashFlow?.cumulative_contributed)}><CartesianGrid stroke="#273449" />
            <XAxis dataKey="date" stroke="#94a3b8" /><YAxis domain={["auto", "auto"]} stroke="#94a3b8" />
            <Tooltip formatter={(v, name) => [`$${Number(v).toLocaleString()}`, name === "contributed" ? "Capital aportado" : "NLV"]} />
            <Line dataKey="nlv" stroke="#38bdf8" dot={false} strokeWidth={2} name="NLV" />
            <Line dataKey="contributed" stroke="#94a3b8" strokeDasharray="4 4" dot={false} name="Capital aportado" />
          </LineChart></ResponsiveContainer></div>}
      </Panel>
    );
  }

  // Dual-line normalized rendering
  const normalizedData = entries?.length ? buildNormalizedData(entries, ibovHistory, cashFlow?.cumulative_contributed) : null;

  return (
    <Panel title="NLV vs Ibovespa — Last 90 Days">
      {!normalizedData ? <EmptyState command="ibkr-positions" /> : (
        <>
          <div style={{ display: "flex", gap: "1rem", marginBottom: "0.75rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", userSelect: "none" }}>
              <input type="checkbox" checked={showNlv} onChange={(e) => setShowNlv(e.target.checked)} />
              <span style={{ color: "#38bdf8" }}>NLV</span>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", userSelect: "none" }}>
              <input type="checkbox" checked={showIbov} onChange={(e) => setShowIbov(e.target.checked)} />
              <span style={{ color: "#94a3b8" }}>Ibovespa</span>
            </label>
          </div>
          <div className="history-chart">
            <ResponsiveContainer>
              <LineChart data={normalizedData}>
                <CartesianGrid stroke="#273449" />
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis domain={["auto", "auto"]} stroke="#94a3b8" tickFormatter={(v) => `${v.toFixed(0)}`} />
                <Tooltip formatter={(v, name) => [`${Number(v).toFixed(2)}`, name === "nlv_normalized" ? "NLV" : "Ibovespa"]} />
                {showNlv && <Line dataKey="nlv_normalized" stroke="#38bdf8" dot={false} strokeWidth={2} name="NLV" connectNulls={false} />}
                {showIbov && <Line dataKey="ibov_normalized" stroke="#94a3b8" dot={false} strokeWidth={2} name="Ibovespa" connectNulls={false} />}
                <Line dataKey="contributed_normalized" stroke="#a78bfa" strokeDasharray="4 4" dot={false} name="Capital aportado" connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </Panel>
  );
}
