import { Panel } from "./Panel";

const labels = { ok: "ok", no_data: "sem dados", stale: "desatualizado", partial: "parcial", estimated: "estimado" };
const classes = { ok: "target-within", estimated: "", partial: "target-near", stale: "target-outside", no_data: "target-outside" };

export default function SourcesPanel({ data, loading, error }) {
  if (!data) {
    return <Panel title="Fontes e atualização"><div className="empty">{error ? "Falha ao carregar as fontes" : loading ? "Carregando fontes…" : "Sem dados de fontes"}</div></Panel>;
  }
  return <Panel title="Fontes e atualização"><div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Estado</th><th>Referência</th><th>Atualizado</th><th>Cobertura</th><th>Próximo passo</th></tr></thead><tbody>
    {data.sources.map((source) => <tr key={source.name}><td>{source.name}</td><td className={classes[source.status] ?? "target-outside"}>{labels[source.status] || source.status}</td><td>{source.as_of || "—"}</td><td>{source.last_updated ? new Date(source.last_updated).toLocaleString() : "—"}</td><td>{source.coverage}</td><td>{source.hint || "—"}</td></tr>)}
  </tbody></table></div></Panel>;
}
