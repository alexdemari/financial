import { Panel } from "./Panel";

/**
 * Parse the first header row of a <table> element and return an object
 * mapping logical column names to their 0-based column index.
 * Returns null if any required column cannot be matched.
 */
function findColumnIndices(tableElement) {
  const headerCells = Array.from(
    tableElement.querySelectorAll("thead tr th")
  ).map((th) => th.textContent.trim().toLowerCase());

  if (headerCells.length === 0) return null;

  const tickerIdx = headerCells.findIndex((h) => h.includes("ticker"));

  // "Preco Atual" contains "preco" but NOT "teto"; "DY Atual" has no "preco"
  const precoIdx = headerCells.findIndex(
    (h) =>
      (h.includes("preco") || h.includes("preço") || h.includes("price")) &&
      !h.includes("teto") &&
      !h.includes("ceiling")
  );

  // "Preco Teto" is the only header containing "teto"
  const tetoIdx = headerCells.findIndex(
    (h) => h.includes("teto") || h.includes("ceiling")
  );

  // "DY Atual" contains "dy" but NOT "min" (excludes "min_dy")
  const dyIdx = headerCells.findIndex(
    (h) => h.includes("dy") && !h.includes("min")
  );

  // "Decisao" — also accept "decision" or "status" for future-proofing
  const statusIdx = headerCells.findIndex(
    (h) =>
      h.includes("decisao") ||
      h.includes("decisão") ||
      h.includes("decision") ||
      h.includes("status")
  );

  if (
    tickerIdx === -1 ||
    precoIdx === -1 ||
    tetoIdx === -1 ||
    dyIdx === -1 ||
    statusIdx === -1
  ) {
    return null;
  }

  return { tickerIdx, precoIdx, tetoIdx, dyIdx, statusIdx };
}

/**
 * Extract data rows from a table given the column indices returned by
 * findColumnIndices.
 */
function extractRows(tableElement, columnIndices) {
  const { tickerIdx, precoIdx, tetoIdx, dyIdx, statusIdx } = columnIndices;
  const bodyRows = tableElement.querySelectorAll("tbody tr");
  const rows = [];

  for (const row of bodyRows) {
    const cells = Array.from(row.querySelectorAll("td")).map((td) =>
      td.textContent.trim()
    );
    if (cells.length === 0) continue;

    rows.push({
      ticker: cells[tickerIdx] ?? "",
      preco: cells[precoIdx] ?? "",
      teto: cells[tetoIdx] ?? "",
      dy: cells[dyIdx] ?? "",
      status: cells[statusIdx] ?? "",
    });
  }

  return rows;
}

/** Colored badge for the Decisão column. */
function StatusBadge({ status }) {
  const statusUpper = status.toUpperCase();
  let badgeStyle;

  if (statusUpper.includes("BUY")) {
    badgeStyle = { background: "#14362e", color: "#34d399" };
  } else if (statusUpper.includes("OVERPRICED")) {
    badgeStyle = { background: "#3b1414", color: "#f87171" };
  } else {
    badgeStyle = { background: "#1e2230", color: "#64748b" };
  }

  return (
    <span
      className="badge"
      style={badgeStyle}
    >
      {status}
    </span>
  );
}

/**
 * Parses the HTML string from dividendReport.html, extracts all tables whose
 * headers contain the expected columns, and renders a compact decision summary
 * above the full markdown report.
 *
 * Degrades silently (returns null) on any parse error or if the expected
 * columns cannot be found.
 */
export default function DividendDecisionTable({ dividendReport }) {
  // Guard: loading state or no report file on disk
  if (!dividendReport || !dividendReport.exists || !dividendReport.html) {
    return null;
  }

  try {
    const doc = new DOMParser().parseFromString(
      dividendReport.html,
      "text/html"
    );
    const tables = doc.querySelectorAll("table");

    const allRows = [];

    for (const table of tables) {
      const columnIndices = findColumnIndices(table);
      if (!columnIndices) continue; // table lacks required columns — skip

      const rows = extractRows(table, columnIndices);
      allRows.push(...rows);
    }

    if (allRows.length === 0) return null;

    return (
      <Panel title="Decisão atual" updated={dividendReport.last_updated}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Preço Atual</th>
                <th>Teto</th>
                <th>DY</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {allRows.map((row) => (
                <tr key={row.ticker}>
                  <td>
                    <strong>{row.ticker}</strong>
                  </td>
                  <td>{row.preco}</td>
                  <td>{row.teto}</td>
                  <td>{row.dy}</td>
                  <td>
                    <StatusBadge status={row.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    );
  } catch {
    // Any parse error — degrade gracefully, never crash the page
    return null;
  }
}
