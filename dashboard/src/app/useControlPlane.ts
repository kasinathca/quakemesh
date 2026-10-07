import { useCallback, useEffect, useRef, useState } from "react";

import { api, dashboardEnvironment } from "../api/client";
import { useTelemetry } from "../telemetry/useTelemetry";
import type { ConnectionState, ScenarioRun, Snapshot } from "../types/contracts";

const emptySnapshot: Snapshot = {
  health: null,
  config: null,
  devices: null,
  events: null,
  alerts: null,
  scenarios: null,
  runs: null,
  session: null,
  activeRun: null,
  lastUpdated: null,
};

export function useControlPlane() {
  const [snapshot, setSnapshot] = useState<Snapshot>(emptySnapshot);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const selectedRun = useRef<string | null>(null);
  const refreshing = useRef(false);

  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const health = await api.health();
      if (health.mode === "AWS") {
        const [devices, events, alerts] = await Promise.all([
          api.devices(),
          api.events(),
          api.alerts(),
        ]);
        const expiresAt = health.expires_at ? Date.parse(health.expires_at) : null;
        setSnapshot({
          health,
          config: null,
          devices: devices.items,
          events: events.items,
          alerts: alerts.items,
          scenarios: [],
          runs: [],
          session: {
            mode: "AWS",
            active_run: null,
            started_at_ms: null,
            expires_at_ms: Number.isNaN(expiresAt) ? null : expiresAt,
            session_id: health.session_id,
            region: health.region,
          },
          activeRun: null,
          lastUpdated: Date.now(),
        });
      } else {
        const [config, devices, events, alerts, scenarios, runs, session] =
          await Promise.all([
          api.config(),
          api.devices(),
          api.events(),
          api.alerts(),
          api.scenarios(),
          api.runs(),
          api.session(),
          ]);
        const runId = selectedRun.current ?? session.active_run?.run_id ?? runs.items[0]?.run_id;
        const activeRun = runId ? await api.run(runId) : null;
        selectedRun.current = activeRun?.run_id ?? null;
        setSnapshot({
          health,
          config,
          devices: devices.items,
          events: events.items,
          alerts: alerts.items,
          scenarios: scenarios.items,
          runs: runs.items,
          session,
          activeRun,
          lastUpdated: Date.now(),
        });
      }
      setConnection("connected");
      setError(null);
    } catch (problem) {
      setConnection("disconnected");
      setError(problem instanceof Error ? problem.message : "Control plane unavailable");
    } finally {
      refreshing.current = false;
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(), 5_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [refresh]);

  useTelemetry({
    enabled: snapshot.health?.mode === "LOCAL",
    onUpdate: refresh,
    onConnected: useCallback(() => setConnection("connected"), []),
    onDisconnected: useCallback(() => {
      setConnection("disconnected");
      void refresh();
    }, [refresh]),
  });

  const start = useCallback(
    async (scenario: string, parameters: Record<string, number>) => {
      if (snapshot.health?.mode === "AWS") throw new Error("Scenario control is unavailable in AWS V2 mode.");
      const run = await api.start({ scenario, source: "dashboard", parameters });
      selectedRun.current = run.run_id;
      setSnapshot((current) => ({ ...current, activeRun: run }));
      await refresh();
      return run;
    },
    [refresh, snapshot.health?.mode],
  );

  const reset = useCallback(async () => {
    if (snapshot.health?.mode === "AWS") throw new Error("Reset is unavailable in AWS V2 mode.");
    await api.reset();
    selectedRun.current = null;
    await refresh();
  }, [refresh, snapshot.health?.mode]);

  const isCloud = snapshot.health?.mode === "AWS" || dashboardEnvironment.label === "AWS V2 Demo";

  const selectRun = useCallback(
    async (run: ScenarioRun) => {
      selectedRun.current = run.run_id;
      setSnapshot((current) => ({ ...current, activeRun: run }));
      await refresh();
    },
    [refresh],
  );

  return {
    snapshot,
    connection,
    error,
    refresh,
    start,
    reset,
    selectRun,
    exportRun: api.exportRun,
    acknowledge: async (alertId: string, deviceId: string) => {
      const result = await api.acknowledge(alertId, deviceId);
      await refresh();
      return result;
    },
    capabilities: {
      scenarioControl: !isCloud,
      scenarioTelemetry: !isCloud,
      reset: !isCloud,
      export: !isCloud,
      cloudReads: isCloud,
    },
    environment: {
      label: dashboardEnvironment.label ?? (isCloud ? "AWS V2 Demo" : "Local V2"),
      region: snapshot.health?.region ?? dashboardEnvironment.region,
      sessionId: snapshot.health?.session_id ?? dashboardEnvironment.sessionId,
      expiresAt: snapshot.health?.expires_at ?? dashboardEnvironment.expiresAt,
    },
  };
}
