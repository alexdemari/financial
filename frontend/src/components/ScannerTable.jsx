import { EmptyState, Panel } from "./Panel";

export default function ScannerTable({ scanner }) {
  return <Panel title="Top Scanner Candidates" updated={scanner?.last_updated}>
    {!scanner?.rows?.length ? <EmptyState command="daily" /> :
      <table><thead><tr><th>Symbol</th><th>Score</th><th>Alignment</th><th>State</th></tr></thead>
      <tbody>{scanner.rows.slice(0, 8).map((row) => <tr key={row.symbol}><td>{row.symbol}</td><td>{row.consistency_score}</td><td>{row.adjusted_alignment}</td><td>{row.market_state}</td></tr>)}</tbody></table>}
  </Panel>;
}
