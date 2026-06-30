export function Updated({ value }) {
  return <span className="updated">Updated: {value ? new Date(value).toLocaleString() : "never"}</span>;
}

export function EmptyState({ command }) {
  return <div className="empty">No data yet — run: <code>just {command}</code></div>;
}

export function Panel({ title, updated, children }) {
  return <section className="panel"><header><h2>{title}</h2><Updated value={updated} /></header>{children}</section>;
}
