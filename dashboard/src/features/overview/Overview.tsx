import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { formatTime, shortId } from "../../theme/format";

export function Overview({ control }: { control: ControlPlane }) {
  const { snapshot } = control;
  const active = snapshot.session?.active_run ?? snapshot.activeRun;
  const values = [
    ["Mode", snapshot.health?.mode],
    ["API health", snapshot.health?.status],
    ["Active run", active?.run_id],
    ["Devices", snapshot.health?.stats?.devices ?? snapshot.devices?.length],
    ["Evidence", snapshot.health?.stats?.evidence],
    ["Events", snapshot.health?.stats?.events ?? snapshot.events?.length],
    ["Alerts", snapshot.health?.stats?.alerts ?? snapshot.alerts?.length],
    ["Confirmation", snapshot.events?.[0]?.status],
  ];
  return (
    <div className="page-stack">
      <div className="metric-grid">
        {values.map(([label, value]) => (
          <article className="metric" key={String(label)}>
            <span>{label}</span>
            <strong>{value === null || value === undefined ? "Unavailable" : shortId(String(value))}</strong>
          </article>
        ))}
      </div>
      <div className="two-column">
        <Panel title="Current experiment" description={control.capabilities.scenarioControl ? "Authoritative local scenario state" : "Scenario control is not exposed by the current AWS V2 API slice"}>
          {snapshot.activeRun ? (
            <dl className="detail-list">
              <div><dt>Run</dt><dd className="mono">{snapshot.activeRun.run_id}</dd></div>
              <div><dt>Scenario</dt><dd>{snapshot.activeRun.scenario}</dd></div>
              <div><dt>Status</dt><dd><StatusBadge value={snapshot.activeRun.status} /></dd></div>
              <div><dt>Expected / observed</dt><dd>{snapshot.activeRun.expected_result} / {snapshot.activeRun.observed_result ?? "Waiting for data"}</dd></div>
            </dl>
          ) : <DataState>{control.capabilities.scenarioControl ? "No scenario run selected" : "Unavailable in AWS V2 mode"}</DataState>}
        </Panel>
        <Panel title="Latest event" description="Most recently updated authoritative event">
          {snapshot.events?.[0] ? (
            <dl className="detail-list">
              <div><dt>Event</dt><dd className="mono">{shortId(snapshot.events[0].event_id, 30)}</dd></div>
              <div><dt>Status</dt><dd><StatusBadge value={snapshot.events[0].status} /></dd></div>
              <div><dt>Provenance</dt><dd>{snapshot.events[0].provenance_type}</dd></div>
              <div><dt>Updated</dt><dd>{formatTime(snapshot.events[0].updated_at_ms)}</dd></div>
            </dl>
          ) : <DataState>{snapshot.events === null ? undefined : "No events recorded"}</DataState>}
        </Panel>
      </div>
    </div>
  );
}
