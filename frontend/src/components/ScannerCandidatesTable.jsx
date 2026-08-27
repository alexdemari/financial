import { useState } from "react";
import MarkdownView from "./MarkdownView";
import { Panel } from "./Panel";

const ACTION_BUCKET_STYLES = {
  candidate:    { background: "#0d2b1e", color: "#34d399" },
  watchlist:    { background: "#2d2008", color: "#fcd34d" },
  avoid:        { background: "#3b1414", color: "#f87171" },
  needs_review: { background: "#1e2230", color: "#94a3b8" },
};

function AccordionRow({ row }) {
  return (
    <tr>
      <td
        colSpan={4}
        style={{
          background: "#0f1117",
          borderBottom: "1px solid #2d3139",
          padding: "10px 16px",
        }}
      >
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "8px 24px",
            margin: 0,
          }}
        >
          {[
            { label: "Lux Role",          value: row.lux_role },
            { label: "SMC Role",          value: row.smc_role },
            { label: "Market State",      value: row.market_state },
            { label: "Adjusted Alignment", value: row.adjusted_alignment },
            { label: "Weekly Lux", value: `${row.weekly_lux_role ?? "—"} · ${row.weekly_lux_trend ?? "—"}` },
            { label: "Weekly SMC", value: `${row.weekly_smc_role ?? "—"} · ${row.weekly_smc_bias ?? "—"}` },
            { label: "Weekly Context", value: row.weekly_smc_context },
            { label: "Weekly Date", value: row.weekly_date },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: "flex", gap: "8px" }}>
              <dt style={{ color: "#64748b", fontWeight: 600, fontSize: "11px", textTransform: "uppercase", whiteSpace: "nowrap" }}>
                {label}
              </dt>
              <dd style={{ margin: 0, color: "#e2e8f0" }}>{value ?? "—"}</dd>
            </div>
          ))}
        </dl>
      </td>
    </tr>
  );
}

function CandidateRow({ row }) {
  const [expanded, setExpanded] = useState(false);
  const bucketStyle = ACTION_BUCKET_STYLES[row.action_bucket] ?? ACTION_BUCKET_STYLES.needs_review;

  return (
    <>
      <tr
        onClick={() => setExpanded((prev) => !prev)}
        style={{ cursor: "pointer" }}
        aria-expanded={expanded}
      >
        <td>
          <strong>{row.symbol}</strong>
        </td>
        <td>
          <span
            style={{
              ...bucketStyle,
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: "9999px",
              fontSize: "11px",
              fontWeight: 600,
            }}
          >
            {row.action_bucket}
          </span>
        </td>
        <td>{row.alignment}</td>
        <td>{row.consistency_score}</td>
      </tr>
      {expanded && <AccordionRow row={row} />}
    </>
  );
}

export default function ScannerCandidatesTable({ scanner, scannerReport }) {
  const rows = scanner?.rows;

  if (!rows?.length) {
    return <MarkdownView report={scannerReport} command="daily" title="Scanner Report" />;
  }

  const sorted_rows = [...rows].sort(
    (a, b) => parseFloat(b.consistency_score ?? 0) - parseFloat(a.consistency_score ?? 0)
  );

  return (
    <Panel title="Scanner Candidates" updated={scanner?.last_updated}>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Action Bucket</th>
              <th>Alignment</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {sorted_rows.map((row) => (
              <CandidateRow key={row.symbol} row={row} />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
