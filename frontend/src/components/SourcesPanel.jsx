import { Panel } from "./Panel";

const labels = { ok: "ok", no_data: "sem dados", stale: "desatualizado", partial: "parcial", estimated: "estimado" };

export default function SourcesPanel({ data }) {
  const sources = data?.sources || [];
  return <Panel title="Fontes e atualização"><div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Estado</th><th>Referência</th><th>Cobertura</th><th>Próximo passo</th></tr></thead><tbody>
    {sources.map((source) => <tr key={source.name}><td>{source.name}</td><td className={`target-${source.status === "ok" ? "within" : "outside"}`}>{labels[source.status] || source.status}</td><td>{source.as_of || "—"}</td><td>{source.coverage}</td><td>{source.hint || "—"}</td></tr>)}
  </tbody></table></div></Panel>;
}
