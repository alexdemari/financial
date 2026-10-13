import { useApi } from "../hooks/useApi";
import AttentionBanner from "./AttentionBanner";
import PatrimonioView from "./PatrimonioView";
import SourcesPanel from "./SourcesPanel";

export default function OverviewView() {
  const patrimonio = useApi("/api/patrimonio");
  const sources = useApi("/api/sources");
  return <><AttentionBanner data={sources.data} /><PatrimonioView data={patrimonio.data} /><SourcesPanel {...sources} /></>;
}
