import { EmptyState, Panel } from "./Panel";

export default function MarkdownView({ report, command, title }) {
  return <Panel title={title} updated={report?.last_updated}>
    {!report?.exists ? <EmptyState command={command} /> : <article className="markdown" dangerouslySetInnerHTML={{ __html: report.html }} />}
  </Panel>;
}
