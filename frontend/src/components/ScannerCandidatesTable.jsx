import MarkdownView from "./MarkdownView";
import { Panel } from "./Panel";

const ACTION_BUCKET_STYLES = {
  candidate: { background: "#0d2b1e", color: "#34d399" },
  watchlist: { background: "#2d2008", color: "#fcd34d" },
  avoid: { background: "#3b1414", color: "#f87171" },
  needs_review: { background: "#1e2230", color: "#94a3b8" },
};

function value(displayValue) {
  return displayValue ?? "—";
}

function Bucket({ row }) {
  const style = ACTION_BUCKET_STYLES[row.action_bucket] ?? ACTION_BUCKET_STYLES.needs_review;
  return <span className="scanner-bucket" style={style}>{value(row.action_bucket)}</span>;
}

function TableNote({ children }) {
  return <p className="scanner-table-note">{children}</p>;
}

function SmcTable({ rows, updated }) {
  return <Panel title="SMC · Daily and Weekly" updated={updated}>
    <TableNote>Market structure and confluence. Daily alignment remains the decision timeframe.</TableNote>
    <div className="table-wrap">
      <table className="timeframe-table smc-timeframe-table">
        <thead>
          <tr>
            <th rowSpan="2">Symbol</th>
            <th rowSpan="2">Bucket</th>
            <th rowSpan="2">Score</th>
            <th rowSpan="2">Alignment</th>
            <th rowSpan="2">Market State</th>
            <th rowSpan="2">Adjusted Alignment</th>
            <th className="timeframe-group" colSpan="3">Daily · 1D</th>
            <th className="timeframe-group" colSpan="3">Weekly · 1W</th>
          </tr>
          <tr>
            <th>Role</th><th>Bias</th><th>Context</th>
            <th>Role</th><th>Bias</th><th>Context</th>
          </tr>
        </thead>
        <tbody>{rows.map((row) => <tr key={`smc-${row.symbol}`}>
          <td><strong>{row.symbol}</strong></td>
          <td><Bucket row={row} /></td>
          <td>{value(row.consistency_score)}</td>
          <td>{value(row.alignment)}</td>
          <td>{value(row.market_state)}</td>
          <td>{value(row.adjusted_alignment)}</td>
          <td>{value(row.smc_role)}</td>
          <td>{value(row.smc_bias)}</td>
          <td>{value(row.smc_context)}</td>
          <td>{value(row.weekly_smc_role)}</td>
          <td>{value(row.weekly_smc_bias)}</td>
          <td>{value(row.weekly_smc_context)}</td>
        </tr>)}</tbody>
      </table>
    </div>
  </Panel>;
}

function LuxTable({ rows, updated }) {
  return <Panel title="Lux · Daily and Weekly" updated={updated}>
    <TableNote>Trend, strength, and signal comparison across the two timeframes.</TableNote>
    <div className="table-wrap">
      <table className="timeframe-table lux-timeframe-table">
        <thead>
          <tr>
            <th rowSpan="2">Symbol</th>
            <th rowSpan="2">Bucket</th>
            <th rowSpan="2">Score</th>
            <th rowSpan="2">Alignment</th>
            <th rowSpan="2">Market State</th>
            <th rowSpan="2">Adjusted Alignment</th>
            <th className="timeframe-group" colSpan="4">Daily · 1D</th>
            <th className="timeframe-group" colSpan="4">Weekly · 1W</th>
          </tr>
          <tr>
            <th>Role</th><th>Trend</th><th>Strength</th><th>Signal</th>
            <th>Role</th><th>Trend</th><th>Strength</th><th>Signal</th>
          </tr>
        </thead>
        <tbody>{rows.map((row) => <tr key={`lux-${row.symbol}`}>
          <td><strong>{row.symbol}</strong></td>
          <td><Bucket row={row} /></td>
          <td>{value(row.consistency_score)}</td>
          <td>{value(row.alignment)}</td>
          <td>{value(row.market_state)}</td>
          <td>{value(row.adjusted_alignment)}</td>
          <td>{value(row.lux_role)}</td>
          <td>{value(row.lux_trend)}</td>
          <td>{value(row.lux_strength)}</td>
          <td>{value(row.lux_signal)}</td>
          <td>{value(row.weekly_lux_role)}</td>
          <td>{value(row.weekly_lux_trend)}</td>
          <td>{value(row.weekly_lux_strength)}</td>
          <td>{value(row.weekly_lux_signal)}</td>
        </tr>)}</tbody>
      </table>
    </div>
  </Panel>;
}

export default function ScannerCandidatesTable({ scanner, scannerReport }) {
  const rows = scanner?.rows;

  if (!rows?.length) {
    return <MarkdownView report={scannerReport} command="daily" title="Scanner Report" />;
  }

  const sortedRows = [...rows].sort(
    (a, b) => parseFloat(b.consistency_score ?? 0) - parseFloat(a.consistency_score ?? 0)
  );

  return <>
    <SmcTable rows={sortedRows} updated={scanner?.last_updated} />
    <LuxTable rows={sortedRows} updated={scanner?.last_updated} />
  </>;
}
