import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api/client";
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
      const [health, config, devices, events, alerts, scenarios, runs, session] =
        await Promise.all([
          api.health(),
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
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useTelemetry({
    onUpdate: refresh,
    onConnected: useCallback(() => setConnection("connected"), []),
    onDisconnected: useCallback(() => {
      setConnection("disconnected");
      void refresh();
    }, [refresh]),
  });

  const start = useCallback(
    async (scenario: string, parameters: Record<string, number>) => {
      const run = await api.start({ scenario, source: "dashboard", parameters });
      selectedRun.current = run.run_id;
      setSnapshot((current) => ({ ...current, activeRun: run }));
      await refresh();
      return run;
    },
    [refresh],
  );

  const reset = useCallback(async () => {
    await api.reset();
    selectedRun.current = null;
    await refresh();
  }, [refresh]);

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
  };
}
