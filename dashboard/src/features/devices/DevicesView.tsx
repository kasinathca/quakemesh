import { useState } from "react";

import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { formatTime, shortId } from "../../theme/format";

export function DevicesView({ control }: { control: ControlPlane }) {
  const devices = control.snapshot.devices;
  const [operatorCredential, setOperatorCredential] = useState("");
  const [pendingDevice, setPendingDevice] = useState<string | null>(null);
  const [lastTestId, setLastTestId] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function send(deviceId: string, reuse = false): Promise<void> {
    const testId = reuse && lastTestId ? lastTestId : crypto.randomUUID();
    setPendingDevice(deviceId);
    setLastTestId(testId);
    setResult(`Requesting ${testId}…`);
    try {
      const response = await control.sendControlledTest(deviceId, testId, operatorCredential);
      setResult(`${response.test.status} · ${response.test.message_label} · ${response.idempotent_replay ? "idempotent replay" : "new request"}`);
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Controlled test failed");
    } finally {
      setPendingDevice(null);
    }
  }

  return <div className="page-stack">
    {control.capabilities.controlledNotifications ? <Panel title="Controlled wireless test" description="Operator-only SNS/FCM delivery check. It never creates an earthquake event or authoritative alert.">
      <div className="evaluation-filters">
        <label>Session operator credential<input type="password" autoComplete="off" value={operatorCredential} onChange={(event) => setOperatorCredential(event.target.value)} placeholder="Operator API key" /></label>
        <div><span>Required label</span><strong>CONTROLLED TEST — NOT AN EARTHQUAKE ALERT</strong><small>The credential remains in this page's memory and is sent only as the API key for this action.</small></div>
      </div>
      {result ? <p className="evaluation-note" role="status">{result}</p> : null}
    </Panel> : null}
    <Panel title="Device registry" description="Safe coarse state only; Firebase tokens and SNS endpoint ARNs are never returned.">
    {devices?.length ? <div className="table-wrap"><table>
      <thead><tr><th>Device ID</th><th>Transport</th><th>Type</th><th>Last seen</th><th>Coarse H3 cell</th><th>Sequence</th><th>State</th><th>Run</th>{control.capabilities.controlledNotifications ? <th>Controlled test</th> : null}</tr></thead>
      <tbody>{devices.map((device) => <tr key={device.device_id}>
        <td className="mono">{device.device_id}</td><td>{device.transport}</td><td>{device.provenance_type}</td><td>{formatTime(device.last_seen_ms)}</td><td className="mono">{device.correlation_cell}</td><td>{device.last_seq}</td><td><StatusBadge value={device.online === false ? "offline" : "active"} /></td><td className="mono">{shortId(device.scenario_run_id)}</td>{control.capabilities.controlledNotifications ? <td><button type="button" disabled={!operatorCredential || !device.online || !device.notification_capable || pendingDevice !== null} onClick={() => void send(device.device_id)}>{pendingDevice === device.device_id ? "Sending…" : "Send test"}</button>{lastTestId && pendingDevice === null ? <button type="button" disabled={!operatorCredential} onClick={() => void send(device.device_id, true)}>Retry same ID</button> : null}</td> : null}
      </tr>)}</tbody>
    </table></div> : <DataState>{devices === null ? undefined : "No devices observed"}</DataState>}
  </Panel></div>;
}
