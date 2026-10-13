import { useApi } from "../hooks/useApi";
import DividendDecisionTable from "./DividendDecisionTable";
import MacroStrip from "./MacroStrip";
import MarkdownView from "./MarkdownView";
import { Panel } from "./Panel";
import ScannerCandidatesTable from "./ScannerCandidatesTable";
import ScannerTable from "./ScannerTable";

export default function AnalysisView() {
  const macro = useApi("/api/macro").data;
  const scanner = useApi("/api/scanner").data;
  const scannerReport = useApi("/api/report/scanner").data;
  const dividendReport = useApi("/api/report/dividends").data;
  return <><Panel title="Macro"><MacroStrip macro={macro} /></Panel><ScannerTable scanner={scanner} /><ScannerCandidatesTable scanner={scanner} scannerReport={scannerReport} /><DividendDecisionTable dividendReport={dividendReport} /><MarkdownView report={dividendReport} command="dividends-local" title="Dividend Report" /></>;
}
