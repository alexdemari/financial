import { EmptyState, Panel } from "./Panel";

export default function RiskAlerts({ risk }) {
  return <Panel title="Risk Alerts" updated={risk?.last_updated}>
    {!risk ? <EmptyState command="ibkr-positions" /> :
      risk.alerts?.length ? <ul className="alerts">{risk.alerts.map((alert, index) => <li key={`${alert.type}-${index}`}>{alert.message}</li>)}</ul>
      : <p className="ok">No active alerts.</p>}
  </Panel>;
}
