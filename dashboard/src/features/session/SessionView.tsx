import type { ControlPlane } from "../../app/types";
import { Panel } from "../../components/Panel";
import { formatTime } from "../../theme/format";

export function SessionView({ control }: { control: ControlPlane }) {
  const session = control.snapshot.session;
  return <Panel title="Session" description="Local sessions do not have an AWS expiry countdown.">
    <dl className="detail-list">
      <div><dt>Mode</dt><dd>{session?.mode ?? "Unavailable"}</dd></div>
      <div><dt>Active run</dt><dd className="mono">{session?.active_run?.run_id ?? "None"}</dd></div>
      <div><dt>Run started</dt><dd>{formatTime(session?.active_run?.started_at_ms)}</dd></div>
      <div><dt>Session expiry</dt><dd>Not applicable in LOCAL mode</dd></div>
    </dl>
  </Panel>;
}
