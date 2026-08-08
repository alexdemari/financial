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
      const colorClass = pct >= 0 ? "text-green-400" : "text-red-400";
      const arrow = pct >= 0 ? "↑" : "↓";
      nlvCell = (
        <div className="flex flex-col items-center px-4 py-2 border-r border-slate-600">
          <span className="text-xs text-slate-400 mb-1">NLV vs ontem</span>
          <span className={`font-semibold ${colorClass}`}>
            {arrow} {sign}{pct.toFixed(1)}%
          </span>
        </div>
      );
    }
  }

  // --- Cell 4: Risk alerts ---
  const riskAlertCount = risk?.alerts?.length ?? null;

  return (
    <div className="flex flex-row items-stretch bg-slate-800 text-white text-sm w-full border-b border-slate-700">
      {/* Cell 1: DTE */}
      <div className="flex flex-col items-center px-4 py-2 border-r border-slate-600">
        <span className="text-xs text-slate-400 mb-1">Opções DTE críticas</span>
        {positions === null ? (
          <span className="text-slate-500">carregando...</span>
        ) : exitOptCount > 0 ? (
          <span className="font-semibold text-amber-400">
            ⚠ {exitOptCount} {exitOptCount === 1 ? "opção" : "opções"} DTE≤7 (EXIT)
          </span>
        ) : (
          <span className="font-semibold text-green-400">✓ Nenhuma opção crítica</span>
        )}
      </div>

      {/* Cell 2: Scanner freshness */}
      <div className="flex flex-col items-center px-4 py-2 border-r border-slate-600">
        <span className="text-xs text-slate-400 mb-1">Scanner</span>
        <span className={`font-semibold ${scannerAmber ? "text-amber-400" : "text-green-400"}`}>
          {scannerAmber && scanner !== null && scanner !== undefined ? `⚠ ${scannerLabel}` : scannerLabel}
        </span>
      </div>

      {/* Cell 3: NLV vs ontem (omitted if insufficient data) */}
      {nlvCell}

      {/* Cell 4: Risk alerts */}
      <div className="flex flex-col items-center px-4 py-2">
        <span className="text-xs text-slate-400 mb-1">Alertas de risco</span>
        {riskAlertCount === null ? (
          <span className="text-slate-500">carregando...</span>
        ) : riskAlertCount === 0 ? (
          <span className="font-semibold text-green-400">— Nenhum alerta</span>
        ) : (
          <span className="font-semibold text-amber-400">⚠ {riskAlertCount} alertas de risco</span>
        )}
      </div>
    </div>
  );
}
