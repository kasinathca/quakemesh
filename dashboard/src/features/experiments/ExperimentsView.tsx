import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { formatTime } from "../../theme/format";

export function ExperimentsView({ control }: { control: ControlPlane }) {
  const runs = control.snapshot.runs;
  return <Panel title="Experiment history" description="Every controlled local execution has one authoritative run record.">
    {runs?.length ? <div className="table-wrap"><table>
      <thead><tr><th>Run</th><th>Scenario</th><th>Source</th><th>Status</th><th>Expected</th><th>Observed</th><th>Devices</th><th>Seed</th><th>Created</th></tr></thead>
      <tbody>{runs.map((run) => <tr key={run.run_id} onClick={() => void control.selectRun(run)}>
        <td className="mono">{run.run_id}</td><td>{run.scenario}</td><td>{run.source}</td><td><StatusBadge value={run.status} /></td><td>{run.expected_result}</td><td>{run.observed_result ?? "Waiting for data"}</td><td>{run.devices}</td><td>{run.seed}</td><td>{formatTime(run.created_at_ms)}</td>
      </tr>)}</tbody>
    </table></div> : <DataState>{runs === null ? undefined : "No experiments recorded"}</DataState>}
  </Panel>;
}
