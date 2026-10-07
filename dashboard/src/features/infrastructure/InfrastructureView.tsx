import type { ControlPlane } from "../../app/types";
import { Panel } from "../../components/Panel";

export function InfrastructureView({ control }: { control: ControlPlane }) {
  const config = control.snapshot.config;
  const cloud = control.capabilities.cloudReads;
  return <div className="page-stack">
    <Panel title={cloud ? "AWS V2 control plane" : "Local control plane"} description={cloud ? "Connection and ownership values are reported by the real AWS V2 API." : "Authoritative local runtime configuration."}>
      <dl className="detail-list">
        <div><dt>Runtime mode</dt><dd>{control.snapshot.health?.mode ?? config?.mode ?? "Unavailable"}</dd></div>
        <div><dt>Application version</dt><dd>{control.snapshot.health?.application_version ?? config?.application_version ?? "Unavailable"}</dd></div>
        <div><dt>Environment</dt><dd>{control.environment.label}</dd></div>
        <div><dt>Region</dt><dd>{control.environment.region ?? "Local"}</dd></div>
        <div><dt>Session</dt><dd className="mono">{control.environment.sessionId ?? "Not applicable"}</dd></div>
        <div><dt>API</dt><dd>{control.connection === "connected" ? "Connected" : "Disconnected"}</dd></div>
        <div><dt>Scenario controls</dt><dd>{control.capabilities.scenarioControl ? "Available" : "Unavailable in AWS V2 mode"}</dd></div>
      </dl>
    </Panel>
    <Panel title="Detector configuration" description={cloud ? "The current AWS read API does not expose detector configuration." : "Authoritative runtime values used by local correlation."}>
      <div className="config-grid">{config ? Object.entries(config.detector).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></div>) : cloud ? "Unavailable in AWS V2 mode" : "Waiting for data"}</div>
    </Panel>
  </div>;
}
