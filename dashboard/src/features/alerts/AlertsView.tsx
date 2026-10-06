import { useState } from "react";

import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { formatTime, shortId } from "../../theme/format";

export function AlertsView({ control }: { control: ControlPlane }) {
  const alerts = control.snapshot.alerts;
  const [error, setError] = useState<string | null>(null);
  async function acknowledge(alertId: string, deviceId: string): Promise<void> {
    setError(null);
    try { await control.acknowledge(alertId, deviceId); }
    catch (problem) { setError(problem instanceof Error ? problem.message : "Acknowledgement failed"); }
  }
  return <Panel title="Alert registry" description="TARGETED means selected locally; it does not claim physical phone receipt.">
    {error ? <div className="inline-error" role="alert">{error}</div> : null}
    {alerts?.length ? <div className="table-wrap"><table>
      <thead><tr><th>Event</th><th>Run</th><th>Device</th><th>Transport</th><th>Status</th><th>Created</th><th>Sent</th><th>Acknowledged</th><th>Failure</th><th>Action</th></tr></thead>
      <tbody>{alerts.map((alert) => <tr key={alert.alert_id}>
        <td className="mono">{shortId(alert.event_id)}</td><td className="mono">{shortId(alert.scenario_run_id)}</td><td className="mono">{alert.device_id}</td><td>{alert.transport}</td><td><StatusBadge value={alert.status} /></td><td>{formatTime(alert.created_at_ms)}</td><td>{formatTime(alert.sent_at_ms)}</td><td>{formatTime(alert.acknowledged_at_ms)}</td><td>{alert.failure_detail ?? "—"}</td><td>{alert.status === "ACKNOWLEDGED" ? "Recorded" : <button onClick={() => void acknowledge(alert.alert_id, alert.device_id)} type="button">Acknowledge</button>}</td>
      </tr>)}</tbody>
    </table></div> : <DataState>{alerts === null ? undefined : "No alert targets recorded"}</DataState>}
  </Panel>;
}
