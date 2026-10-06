import type { ControlPlane } from "../../app/types";
import { Panel } from "../../components/Panel";

export function InfrastructureView({ control }: { control: ControlPlane }) {
  const config = control.snapshot.config;
  return <div className="page-stack">
    <Panel title="Local control plane" description="This phase intentionally contains no live AWS deployment state.">
      <dl className="detail-list">
        <div><dt>Runtime mode</dt><dd>{config?.mode ?? "Unavailable"}</dd></div>
        <div><dt>Application version</dt><dd>{config?.application_version ?? "Unavailable"}</dd></div>
        <div><dt>Active-run policy</dt><dd>{config ? `${config.scenario_policy.maximum_active_runs} controlled run` : "Unavailable"}</dd></div>
        <div><dt>Cancellation</dt><dd>{config?.scenario_policy.cancellation_supported ? "Supported" : "Not implemented"}</dd></div>
      </dl>
    </Panel>
    <Panel title="Detector configuration" description="Authoritative runtime values used by local correlation.">
      <div className="config-grid">{config ? Object.entries(config.detector).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></div>) : "Waiting for data"}</div>
    </Panel>
  </div>;
}
