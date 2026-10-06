import { Check, Clipboard, Download, Play, RotateCcw, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { StatusBadge } from "../../components/StatusBadge";
import { EventMap } from "../map/EventMap";
import { formatTime, shortId } from "../../theme/format";
import type { ScenarioStage } from "../../types/contracts";

const gateCodes = new Set([
  "REPLAY_GATE_EVALUATED",
  "MOTION_GATE_EVALUATED",
  "RECENCY_GATE_EVALUATED",
  "DEVICE_DIVERSITY_GATE_EVALUATED",
  "SPATIAL_DIVERSITY_GATE_EVALUATED",
  "COHERENCE_GATE_EVALUATED",
  "TARGETING_EVALUATED",
]);

function downloadStages(stages: ScenarioStage[]): void {
  const blob = new Blob([JSON.stringify(stages, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "quakemesh-telemetry.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ScenarioLab({ control }: { control: ControlPlane }) {
  const catalog = control.snapshot.scenarios ?? [];
  const run = control.snapshot.activeRun;
  const [scenarioId, setScenarioId] = useState("distributed");
  const [parameterValues, setParameterValues] = useState<Record<string, Record<string, number>>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [exportPath, setExportPath] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("all");
  const [autoscroll, setAutoscroll] = useState(true);
  const logContainer = useRef<HTMLDivElement>(null);
  const selected = catalog.find((item) => item.id === scenarioId) ?? catalog[0];

  const defaultParameters = useMemo(
    () => Object.fromEntries((selected?.supported_parameters ?? []).map((parameter) => [parameter.name, parameter.default])),
    [selected],
  );
  const parameters = parameterValues[scenarioId] ?? defaultParameters;

  const stages = useMemo(() => run?.stages ?? [], [run?.stages]);
  const logs = useMemo(() => stages.filter((stage) => {
    const haystack = `${stage.component} ${stage.code} ${stage.message} ${stage.device_id ?? ""}`.toLowerCase();
    return (severity === "all" || stage.severity === severity) && haystack.includes(search.toLowerCase());
  }), [search, severity, stages]);
  const gates = useMemo(
    () => Array.from(
      new Map(
        stages
          .filter((stage) => gateCodes.has(stage.code))
          .map((stage) => [stage.code, stage]),
      ).values(),
    ),
    [stages],
  );
  const runEvent = control.snapshot.events?.find((event) => event.scenario_run_id === run?.run_id) ?? null;
  const isActive = run?.status === "RUNNING" || run?.status === "QUEUED";
  const verdict = run?.observed_result
    ? run.expected_result === "CONDITIONAL" || run.expected_result === run.observed_result
      ? "EXPECTED RESULT OBSERVED"
      : "RESULT DID NOT MATCH EXPECTATION"
    : "WAITING FOR EVALUATION";

  useEffect(() => {
    if (autoscroll && logs.length && logContainer.current) {
      logContainer.current.scrollTop = logContainer.current.scrollHeight;
    }
  }, [autoscroll, logs]);

  async function perform(action: () => Promise<unknown>): Promise<void> {
    setActionError(null);
    try {
      await action();
    } catch (problem) {
      setActionError(problem instanceof Error ? problem.message : "Operation failed");
    }
  }

  return (
    <div className="page-stack scenario-page">
      <Panel
        title="Scenario catalog"
        description="Controlled experiments use the same authoritative service as CLI and future clients."
      >
        {catalog.length ? (
          <div className="catalog-grid">
            {catalog.map((scenario) => (
              <button
                className={scenario.id === scenarioId ? "scenario-card selected" : "scenario-card"}
                key={scenario.id}
                onClick={() => setScenarioId(scenario.id)}
                type="button"
              >
                <strong>{scenario.title}</strong>
                <span>{scenario.purpose}</span>
                <small>Expected: {scenario.expected_result}</small>
              </button>
            ))}
          </div>
        ) : <DataState />}
      </Panel>

      <div className="two-column scenario-control-grid">
        <Panel title="Validated parameters" description="Only simulator-backed catalog parameters are accepted.">
          {selected ? (
            <div className="parameter-form">
              {selected.supported_parameters.map((parameter) => (
                <label key={parameter.name}>
                  <span>{parameter.name.replaceAll("_", " ")}</span>
                  <input
                    type="number"
                    min={parameter.minimum}
                    max={parameter.maximum}
                    step={parameter.type === "integer" ? 1 : 0.01}
                    value={parameters[parameter.name] ?? parameter.default}
                    onChange={(event) => setParameterValues((current) => ({
                      ...current,
                      [scenarioId]: {
                        ...(current[scenarioId] ?? defaultParameters),
                        [parameter.name]: Number(event.target.value),
                      },
                    }))}
                  />
                  <small>{parameter.minimum}–{parameter.maximum} {parameter.unit}</small>
                </label>
              ))}
              <div className="button-row">
                <button
                  className="primary"
                  disabled={isActive}
                  onClick={() => perform(() => control.start(selected.id, parameters))}
                  type="button"
                ><Play size={16} /> Start</button>
                <button disabled={isActive} onClick={() => perform(control.reset)} type="button">
                  <RotateCcw size={16} /> Reset
                </button>
                <button
                  disabled={!run || isActive}
                  onClick={() => perform(async () => {
                    if (!run) return;
                    const result = await control.exportRun(run.run_id);
                    setExportPath(result.path);
                  })}
                  type="button"
                ><Download size={16} /> Export evidence</button>
              </div>
              {actionError ? <div className="inline-error" role="alert">{actionError}</div> : null}
              {exportPath ? <p className="export-path">Exported to <code>{exportPath}</code></p> : null}
            </div>
          ) : <DataState />}
        </Panel>

        <Panel title="Live run" description={run ? run.run_id : "No run selected"}>
          {run ? (
            <>
              <div className="run-grid">
                <div><span>Status</span><div data-testid="run-status"><StatusBadge value={run.status} /></div></div>
                <div><span>Source</span><strong>{run.source}</strong></div>
                <div><span>Expected</span><strong>{run.expected_result}</strong></div>
                <div><span>Observed</span><strong data-testid="run-observed">{run.observed_result ?? "Waiting for data"}</strong></div>
              </div>
              <div className="verdict"><Check size={18} /><div><span>Evaluation</span><strong>{verdict}</strong></div></div>
            </>
          ) : <DataState>No scenario run selected</DataState>}
        </Panel>
      </div>

      <Panel title="Gate evaluation" description="Backend-emitted evaluation stages; failures remain visible.">
        {gates.length ? (
          <div className="gate-grid">
            {gates.map((stage) => (
              <article key={stage.stage_id}>
                <StatusBadge value={stage.status} />
                <strong>{stage.code.replaceAll("_", " ")}</strong>
                <span>{stage.message}</span>
                <code>{JSON.stringify(stage.data)}</code>
              </article>
            ))}
          </div>
        ) : <DataState>Waiting for gate telemetry</DataState>}
      </Panel>

      <div className="two-column stage-map-grid">
        <Panel title="Stage timeline" description="Ordered authoritative state and detector operations.">
          {stages.length ? (
            <ol className="timeline">
              {stages.map((stage) => (
                <li key={stage.stage_id} className={`severity-${stage.severity}`}>
                  <time>{formatTime(stage.occurred_at_ms)}</time>
                  <div><strong>{stage.sequence}. {stage.code.replaceAll("_", " ")}</strong><p>{stage.message}</p></div>
                </li>
              ))}
            </ol>
          ) : <DataState />}
        </Panel>
        <Panel title="Map evolution" description={runEvent ? shortId(runEvent.event_id, 32) : "No confirmed event"}>
          <EventMap event={runEvent} />
        </Panel>
      </div>

      <Panel
        title="Structured live log"
        description="Every row is backend stage telemetry."
        action={<div className="log-actions">
          <button onClick={() => void navigator.clipboard.writeText(JSON.stringify(logs, null, 2))} type="button"><Clipboard size={15} /> Copy</button>
          <button onClick={() => downloadStages(logs)} type="button"><Download size={15} /> Export</button>
        </div>}
      >
        <div className="log-toolbar">
          <label className="search-box"><Search size={16} /><input aria-label="Search logs" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search telemetry" /></label>
          <select aria-label="Filter severity" value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="all">All severities</option><option value="info">Info</option><option value="warning">Warning</option><option value="error">Error</option>
          </select>
          <label className="check-label"><input type="checkbox" checked={autoscroll} onChange={(event) => setAutoscroll(event.target.checked)} /> Autoscroll</label>
        </div>
        <div className="table-wrap log-table-wrap" ref={logContainer}>
          <table>
            <thead><tr><th>Timestamp</th><th>Component</th><th>Stage</th><th>Severity</th><th>Device</th><th>Run</th><th>Message</th></tr></thead>
            <tbody>{logs.map((stage) => <tr key={stage.stage_id}>
              <td>{formatTime(stage.occurred_at_ms)}</td><td>{stage.component}</td><td>{stage.code}</td><td><StatusBadge value={stage.severity} /></td><td className="mono">{shortId(stage.device_id)}</td><td className="mono">{shortId(stage.run_id)}</td><td>{stage.message}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
