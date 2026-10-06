import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { formatTime, shortId } from "../../theme/format";

export function DevicesView({ control }: { control: ControlPlane }) {
  const devices = control.snapshot.devices;
  return <Panel title="Device registry" description="Safe coarse state only; credentials and raw coordinates are never returned.">
    {devices?.length ? <div className="table-wrap"><table>
      <thead><tr><th>Device ID</th><th>Transport</th><th>Type</th><th>Last seen</th><th>Coarse H3 cell</th><th>Sequence</th><th>State</th><th>Run</th></tr></thead>
      <tbody>{devices.map((device) => <tr key={device.device_id}>
        <td className="mono">{device.device_id}</td><td>{device.transport}</td><td>{device.provenance_type}</td><td>{formatTime(device.last_seen_ms)}</td><td className="mono">{device.correlation_cell}</td><td>{device.last_seq}</td><td><StatusBadge value="active" /></td><td className="mono">{shortId(device.scenario_run_id)}</td>
      </tr>)}</tbody>
    </table></div> : <DataState>{devices === null ? undefined : "No devices observed"}</DataState>}
  </Panel>;
}
