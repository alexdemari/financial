const cellStyle = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  padding: "8px 16px",
  borderRight: "1px solid #2d3139",
};
const lastCellStyle = { ...cellStyle, borderRight: "none" };
const labelStyle = { fontSize: "11px", color: "#64748b", marginBottom: "4px" };
const bannerStyle = {
  display: "flex",
  flexDirection: "row",
  alignItems: "stretch",
  background: "#151820",
  color: "#e2e8f0",
  fontSize: "13px",
  width: "100%",
  borderBottom: "1px solid #2d3139",
};
const green = { fontWeight: 600, color: "#34d399" };
const amber = { fontWeight: 600, color: "#fcd34d" };
const muted = { color: "#64748b" };

export default function AttentionBanner({ risk, scanner, positions, recentHistory }) {
  // --- Cell 1: DTE alert ---
  const exitOptCount =
    positions?.filter((p) => p.asset_type === "OPT" && p.risk_status === "EXIT").length ?? 0;

  // --- Cell 2: Scanner freshness ---
  let scannerLabel = "carregando...";
  let scannerAmber = false;
  if (scanner !== null && scanner !== undefined) {
    if (!scanner.last_updated) {
      scannerLabel = "sem dados";
      scannerAmber = true;
    } else {
      const lastUpdatedDate = new Date(scanner.last_updated);
      const nowDate = new Date();
      const diffMs = nowDate - lastUpdatedDate;
      const diffHours = diffMs / (1000 * 60 * 60);
      if (diffHours < 24) {
        const hh = String(lastUpdatedDate.getHours()).padStart(2, "0");
        const mm = String(lastUpdatedDate.getMinutes()).padStart(2, "0");
        scannerLabel = `atualizado hoje ${hh}:${mm}`;
        scannerAmber = false;
      } else {
        const wholeHours = Math.floor(diffHours);
        scannerLabel = `desatualizado (${wholeHours}h atrás)`;
        scannerAmber = true;
      }
    }
  }

  // --- Cell 3: NLV vs ontem ---
  let nlvCell = null;
  if (recentHistory && recentHistory.length >= 2) {
    const sorted = [...recentHistory].sort((a, b) => {
      const dateA = new Date(a.date);
      const dateB = new Date(b.date);
      return dateA - dateB;
    });
    const prev = sorted[sorted.length - 2];
    const last = sorted[sorted.length - 1];
    if (prev.nlv != null && last.nlv != null && prev.nlv !== 0) {
      const pct = ((last.nlv - prev.nlv) / prev.nlv) * 100;
      const sign = pct >= 0 ? "+" : "";
      const arrow = pct >= 0 ? "↑" : "↓";
      nlvCell = (
        <div style={cellStyle}>
          <span style={labelStyle}>NLV vs ontem</span>
          <span style={pct >= 0 ? green : { fontWeight: 600, color: "#f87171" }}>
            {arrow} {sign}{pct.toFixed(1)}%
          </span>
        </div>
      );
    }
  }

  // --- Cell 4: Risk alerts ---
  const riskAlertCount = risk?.alerts?.length ?? null;

  return (
    <div style={bannerStyle}>
      {/* Cell 1: DTE */}
      <div style={cellStyle}>
        <span style={labelStyle}>Opções DTE críticas</span>
        {positions === null ? (
          <span style={muted}>carregando...</span>
        ) : exitOptCount > 0 ? (
          <span style={amber}>
            ⚠ {exitOptCount} {exitOptCount === 1 ? "opção" : "opções"} DTE≤7 (EXIT)
          </span>
        ) : (
          <span style={green}>✓ Nenhuma opção crítica</span>
        )}
      </div>

      {/* Cell 2: Scanner freshness */}
      <div style={cellStyle}>
        <span style={labelStyle}>Scanner</span>
        <span style={scannerAmber ? amber : green}>
          {scannerAmber && scanner !== null && scanner !== undefined ? `⚠ ${scannerLabel}` : scannerLabel}
        </span>
      </div>

      {/* Cell 3: NLV vs ontem (omitted if insufficient data) */}
      {nlvCell}

      {/* Cell 4: Risk alerts */}
      <div style={lastCellStyle}>
        <span style={labelStyle}>Alertas de risco</span>
        {riskAlertCount === null ? (
          <span style={muted}>carregando...</span>
        ) : riskAlertCount === 0 ? (
          <span style={green}>— Nenhum alerta</span>
        ) : (
          <span style={amber}>⚠ {riskAlertCount} alertas de risco</span>
        )}
      </div>
    </div>
  );
}
