import { z } from "zod";

import type {
  AlertRecord,
  DeviceRecord,
  EventRecord,
  Health,
  RuntimeConfig,
  ScenarioDefinition,
  ScenarioRun,
  SessionInfo,
} from "../types/contracts";

declare global {
  interface Window {
    QUAKEMESH_CONFIG?: {
      apiBaseUrl?: string;
      apiKey?: string;
      environmentLabel?: string;
      region?: string;
      sessionId?: string;
      expiresAt?: string;
    };
  }
}

const envelopeSchema = z.object({
  schema_version: z.literal("2.0"),
  request_id: z.string().min(1),
  data: z.unknown(),
});

const errorSchema = z.object({
  schema_version: z.literal("2.0"),
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string(),
    details: z.record(z.string(), z.unknown()),
  }),
});

export const API_BASE = (
  window.QUAKEMESH_CONFIG?.apiBaseUrl ??
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

export const dashboardEnvironment = {
  label: window.QUAKEMESH_CONFIG?.environmentLabel,
  region: window.QUAKEMESH_CONFIG?.region,
  sessionId: window.QUAKEMESH_CONFIG?.sessionId,
  expiresAt: window.QUAKEMESH_CONFIG?.expiresAt,
};

export class ApiProblem extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = window.QUAKEMESH_CONFIG?.apiKey;
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (apiKey && init?.method && init.method !== "GET") headers.set("x-api-key", apiKey);
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers,
  });
  const raw: unknown = await response.json();
  if (!response.ok) {
    const parsed = errorSchema.safeParse(raw);
    if (parsed.success) {
      throw new ApiProblem(parsed.data.error.message, parsed.data.error.code, response.status);
    }
    throw new ApiProblem(`Request failed with HTTP ${response.status}`, "HTTP_ERROR", response.status);
  }
  return envelopeSchema.parse(raw).data as T;
}

export const api = {
  health: () => request<Health>("/health"),
  config: () => request<RuntimeConfig>("/v1/config"),
  devices: () => request<{ items: DeviceRecord[] }>("/v1/devices"),
  events: () => request<{ items: EventRecord[] }>("/v1/events"),
  alerts: () => request<{ items: AlertRecord[] }>("/v1/alerts"),
  scenarios: () => request<{ items: ScenarioDefinition[] }>("/v1/scenarios"),
  runs: () => request<{ items: ScenarioRun[] }>("/v1/scenario-runs"),
  run: (runId: string) => request<ScenarioRun>(`/v1/scenario-runs/${encodeURIComponent(runId)}`),
  session: () => request<SessionInfo>("/v1/session"),
  start: (body: Record<string, unknown>) =>
    request<ScenarioRun>("/v1/demo/scenario-runs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reset: () =>
    request<{ deleted: Record<string, number>; physical_records_preserved: boolean }>(
      "/v1/demo/reset",
      { method: "POST", body: "{}" },
    ),
  exportRun: (runId: string) =>
    request<{ run_id: string; path: string; format: string }>(
      `/v1/demo/scenario-runs/${encodeURIComponent(runId)}/export`,
      { method: "POST", body: "{}" },
    ),
  acknowledge: (alertId: string, deviceId: string) =>
    request<{ alert: AlertRecord; transition_created: boolean }>(
      `/v1/alerts/${encodeURIComponent(alertId)}/ack`,
      {
        method: "POST",
        body: JSON.stringify({ acknowledgement_source: "dashboard", device_id: deviceId }),
      },
    ),
};
