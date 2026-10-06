import { useState } from "react";

import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { formatTime, shortId } from "../../theme/format";

export function EventsView({ control }: { control: ControlPlane }) {
  const events = control.snapshot.events;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = events?.find((event) => event.event_id === selectedId) ?? events?.[0];
  const relatedAlerts = control.snapshot.alerts?.filter((alert) => alert.event_id === selected?.event_id) ?? [];
  return (
    <div className="page-stack">
      <Panel title="Event registry" description="Confirmed and resolved events with experiment provenance.">
        {events?.length ? <div className="table-wrap"><table>
          <thead><tr><th>Event</th><th>Status</th><th>Provenance</th><th>Run</th><th>Devices</th><th>Evidence</th><th>Updated</th></tr></thead>
          <tbody>{events.map((event) => <tr className={selected?.event_id === event.event_id ? "selected-row" : ""} key={event.event_id} onClick={() => setSelectedId(event.event_id)}>
            <td className="mono">{shortId(event.event_id, 26)}</td><td><StatusBadge value={event.status} /></td><td>{event.provenance_type}</td><td className="mono">{shortId(event.scenario_run_id)}</td><td>{event.device_ids.length}</td><td>{event.evidence_ids.length}</td><td>{formatTime(event.updated_at_ms)}</td>
          </tr>)}</tbody>
        </table></div> : <DataState>{events === null ? undefined : "No events recorded"}</DataState>}
      </Panel>
      <Panel title="Event detail" description={selected?.event_id}>
        {selected ? <div className="detail-sections">
          <dl className="detail-list">
            <div><dt>Status</dt><dd><StatusBadge value={selected.status} /></dd></div>
            <div><dt>Run provenance</dt><dd className="mono">{selected.scenario_run_id ?? "Physical / unowned"}</dd></div>
            <div><dt>Lifecycle</dt><dd>{formatTime(selected.first_observed_at_ms)} → {formatTime(selected.updated_at_ms)}</dd></div>
            <div><dt>Version</dt><dd>{selected.version}</dd></div>
            <div><dt>Evidence count</dt><dd>{selected.evidence_ids.length}</dd></div>
            <div><dt>Related alerts</dt><dd>{relatedAlerts.length}</dd></div>
          </dl>
          <div><h3>Devices</h3><div className="token-list">{selected.device_ids.map((value) => <code key={value}>{value}</code>)}</div></div>
          <div><h3>Detection footprint</h3><div className="token-list">{selected.detection_footprint.map((value) => <code key={value}>{value}</code>)}</div></div>
          <div><h3>Warning frontier</h3><div className="token-list">{selected.warning_frontier.map((value) => <code key={value}>{value}</code>)}</div></div>
        </div> : <DataState />}
      </Panel>
    </div>
  );
}
