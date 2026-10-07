export type ConnectionState = "connecting" | "connected" | "disconnected";

export interface Stats {
  devices: number;
  evidence: number;
  events: number;
  alerts: number;
  scenario_runs: number;
  scenario_stages: number;
}

export interface Health {
  status: string;
  mode: "LOCAL" | "AWS";
  application_version: string;
  stats?: Stats;
  session_id?: string;
  region?: string;
  expires_at?: string;
}

export interface DetectorConfig {
  [key: string]: number;
}

export interface RuntimeConfig {
  mode: "LOCAL";
  application_version: string;
  detector: DetectorConfig;
  scenario_policy: {
    maximum_active_runs: number;
    cancellation_supported: boolean;
  };
}

export interface ParameterSpec {
  name: string;
  type: "integer" | "number";
  default: number;
  minimum: number;
  maximum: number;
  unit: string;
}

export interface ScenarioDefinition {
  id: string;
  title: string;
  purpose: string;
  expected_result: string;
  supported_parameters: ParameterSpec[];
}

export interface ScenarioStage {
  stage_id: number;
  run_id: string;
  sequence: number;
  occurred_at_ms: number;
  code: string;
  component: string;
  severity: "info" | "warning" | "error";
  status: string;
  message: string;
  data: Record<string, unknown>;
  device_id: string | null;
  event_id: string | null;
  alert_id: string | null;
  duration_ms: number | null;
}

export interface ScenarioRun {
  run_id: string;
  scenario: string;
  source: string;
  mode: string;
  catalog_version: string;
  seed: number;
  devices: number;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  expected_result: string;
  observed_result: string | null;
  created_at_ms: number;
  started_at_ms: number | null;
  completed_at_ms: number | null;
  parameters: Record<string, number>;
  event_ids: string[];
  error: string | null;
  stages?: ScenarioStage[];
}

export interface PolygonView {
  cell: string;
  boundary: [number, number][];
}

export interface EventRecord {
  event_id: string;
  status: string;
  provenance_type: "physical" | "scenario";
  scenario_run_id: string | null;
  created_at_ms: number;
  updated_at_ms: number;
  first_observed_at_ms: number;
  last_observed_at_ms: number;
  version: number;
  device_ids: string[];
  detection_footprint: string[];
  warning_frontier: string[];
  evidence_ids: string[];
  footprint_polygons: PolygonView[];
  frontier_polygons: PolygonView[];
}

export interface DeviceRecord {
  device_id: string;
  correlation_cell: string;
  last_seen_ms: number;
  last_seq: number;
  transport: string;
  provenance_type: string;
  scenario_run_id: string | null;
}

export interface AlertRecord {
  alert_id: string;
  event_id: string;
  event_version: number;
  device_id: string;
  created_at_ms: number;
  sent_at_ms?: number | null;
  acknowledged_at_ms: number | null;
  acknowledgement_source: string | null;
  transport?: string;
  status: string;
  failure_detail?: string | null;
  provenance_type: string;
  scenario_run_id: string | null;
}

export interface SessionInfo {
  mode: "LOCAL" | "AWS";
  active_run: ScenarioRun | null;
  started_at_ms: number | null;
  expires_at_ms: number | null;
  session_id?: string;
  region?: string;
}

export interface Snapshot {
  health: Health | null;
  config: RuntimeConfig | null;
  devices: DeviceRecord[] | null;
  events: EventRecord[] | null;
  alerts: AlertRecord[] | null;
  scenarios: ScenarioDefinition[] | null;
  runs: ScenarioRun[] | null;
  session: SessionInfo | null;
  activeRun: ScenarioRun | null;
  lastUpdated: number | null;
}
