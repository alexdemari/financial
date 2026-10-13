const bannerStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "8px 24px",
  padding: "8px 16px",
  background: "#151820",
  borderBottom: "1px solid #2d3139",
  fontSize: "13px",
};
const amber = { fontWeight: 600, color: "#fcd34d" };
const green = { fontWeight: 600, color: "#34d399" };

// Stale/missing real-data sources and critical option expirations; "estimated"
// manual sources are expected to be hand-edited, so they are not alerts.
export default function AttentionBanner({ data }) {
  if (!data) return null;
  const exitOptions = data.alerts?.exit_options;
  const attention = (data.sources || []).filter((source) => ["stale", "no_data", "partial"].includes(source.status));
  if (!attention.length && !exitOptions) return <div style={bannerStyle}><span style={green}>✓ Sem alertas</span></div>;
  return <div style={bannerStyle}>
    {exitOptions > 0 && <span style={amber}>⚠ {exitOptions} {exitOptions === 1 ? "opção" : "opções"} DTE≤7 (EXIT)</span>}
    {attention.map((source) => <span style={amber} key={source.name}>⚠ {source.name}: {source.status === "stale" ? "desatualizada" : source.status === "partial" ? "parcial" : "sem dados"}</span>)}
  </div>;
}
