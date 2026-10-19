import { Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";

type Outcome = "TP" | "TN" | "FP" | "FN";
interface Trial {
  trial_id: string;
  scenario: string;
  seed: number;
  truth_positive: boolean;
  predicted_positive: boolean;
  outcome: Outcome;
  packet_loss_fraction: number;
  jitter_ms: number;
  devices: number;
  confirmation_latency_ms: number | null;
  alert_target_latency_ms: number | null;
  transport_delivery_success_ratio: number | null;
  notification_receipt_status: string;
  failure: string | null;
}
interface Summary {
  result_kind: string;
  disclaimer: string;
  generated_at: string;
  trial_counts: { requested: number; completed: number; failed: number };
  reproducibility: { geo_index: string; detector: Record<string, number> };
}

function ratio(numerator: number, denominator: number): number | null {
  return denominator ? numerator / denominator : null;
}

function metric(value: number | null): string {
  return value === null ? "Undefined" : `${(value * 100).toFixed(1)}%`;
}

function save(name: string, type: string, body: string): void {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csv(trials: Trial[]): string {
  const fields: Array<keyof Trial> = ["trial_id", "scenario", "seed", "truth_positive", "predicted_positive", "outcome", "packet_loss_fraction", "jitter_ms", "devices", "confirmation_latency_ms", "alert_target_latency_ms", "transport_delivery_success_ratio", "notification_receipt_status", "failure"];
  return `${fields.join(",")}\n${trials.map((row) => fields.map((field) => JSON.stringify(row[field] ?? "")).join(",")).join("\n")}\n`;
}

export function EvaluationView() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trials, setTrials] = useState<Trial[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState("all");
  const [network, setNetwork] = useState("all");

  useEffect(() => {
    const root = `${import.meta.env.BASE_URL}evaluation/`;
    Promise.all([
      fetch(`${root}latest.json`).then((response) => response.ok ? response.json() as Promise<Summary> : Promise.reject(new Error(`summary HTTP ${response.status}`))),
      fetch(`${root}trials.json`).then((response) => response.ok ? response.json() as Promise<Trial[]> : Promise.reject(new Error(`trials HTTP ${response.status}`))),
    ]).then(([nextSummary, nextTrials]) => {
      setSummary(nextSummary);
      setTrials(nextTrials);
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Evaluation artifacts unavailable"));
  }, []);

  const filtered = useMemo(() => (trials ?? []).filter((trial) =>
    (scenario === "all" || trial.scenario === scenario) &&
    (network === "all" || (network === "degraded" ? trial.packet_loss_fraction > 0 || trial.jitter_ms > 0 : trial.packet_loss_fraction === 0 && trial.jitter_ms === 0)),
  ), [trials, scenario, network]);
  const counts = useMemo(() => Object.fromEntries((["TP", "TN", "FP", "FN"] as Outcome[]).map((key) => [key, filtered.filter((row) => row.outcome === key).length])) as Record<Outcome, number>, [filtered]);
  const accuracy = ratio(counts.TP + counts.TN, filtered.length);
  const precision = ratio(counts.TP, counts.TP + counts.FP);
  const recall = ratio(counts.TP, counts.TP + counts.FN);
  const specificity = ratio(counts.TN, counts.TN + counts.FP);
  const f1 = ratio(2 * counts.TP, 2 * counts.TP + counts.FP + counts.FN);
  const falsePositiveRate = ratio(counts.FP, counts.FP + counts.TN);
  const falseNegativeRate = ratio(counts.FN, counts.FN + counts.TP);
  const conditionGroups = useMemo(() => {
    const groups = new Map<string, Trial[]>();
    filtered.forEach((trial) => {
      const key = `${trial.scenario} · loss ${trial.packet_loss_fraction} · jitter ${trial.jitter_ms} ms`;
      groups.set(key, [...(groups.get(key) ?? []), trial]);
    });
    return [...groups].map(([label, rows]) => ({
      label,
      accuracy: rows.filter((row) => row.truth_positive === row.predicted_positive).length / rows.length,
      trials: rows.length,
    }));
  }, [filtered]);

  function exportPng(): void {
    const canvas = document.createElement("canvas");
    canvas.width = 1000;
    canvas.height = 720;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#172b35";
    context.textAlign = "center";
    context.font = "bold 30px sans-serif";
    context.fillText("QuakeMesh offline synthetic confusion matrix", 500, 55);
    context.font = "18px sans-serif";
    context.fillText(`Filter: ${scenario} / ${network} · n=${filtered.length}`, 500, 90);
    const boxes: Array<[Outcome, number, number]> = [["TP", 190, 180], ["FN", 520, 180], ["FP", 190, 400], ["TN", 520, 400]];
    const max = Math.max(1, ...Object.values(counts));
    boxes.forEach(([label, x, y]) => {
      context.fillStyle = `rgba(24, 111, 130, ${0.18 + 0.78 * counts[label] / max})`;
      context.fillRect(x, y, 280, 170);
      context.fillStyle = "#172b35";
      context.font = "bold 32px sans-serif";
      context.fillText(label, x + 140, y + 70);
      context.font = "42px sans-serif";
      context.fillText(String(counts[label]), x + 140, y + 125);
    });
    context.font = "17px sans-serif";
    context.fillText("Synthetic software evaluation — not real-world earthquake accuracy", 500, 650);
    const anchor = document.createElement("a");
    anchor.href = canvas.toDataURL("image/png");
    anchor.download = "quakemesh-synthetic-confusion-matrix.png";
    anchor.click();
  }

  if (error) return <Panel title="Evaluation / Metrics" description="Offline synthetic experiment artifacts"><DataState>Evaluation artifacts are unavailable: {error}</DataState></Panel>;
  if (!summary || !trials) return <Panel title="Evaluation / Metrics"><DataState /></Panel>;

  return <div className="page-stack evaluation-page">
    <div className="evaluation-disclaimer" role="note"><strong>Offline synthetic simulation results.</strong> {summary.disclaimer}</div>
    <Panel title="Dataset and filters" description={`Generated ${new Date(summary.generated_at).toLocaleString()} · ${summary.reproducibility.geo_index}`} action={<div className="button-row evaluation-actions">
      <button type="button" onClick={() => save("quakemesh-evaluation-filtered.csv", "text/csv", csv(filtered))}><Download size={15} />CSV</button>
      <button type="button" onClick={() => save("quakemesh-evaluation-filtered.json", "application/json", JSON.stringify({ sourceSummary: summary, filter: { scenario, network }, confusionMatrix: counts, metrics: { accuracy, precision, recall, specificity, f1, falsePositiveRate, falseNegativeRate }, trials: filtered }, null, 2))}><Download size={15} />JSON</button>
      <button type="button" onClick={exportPng}><Download size={15} />PNG</button>
    </div>}>
      <div className="evaluation-filters">
        <label>Scenario<select value={scenario} onChange={(event) => setScenario(event.target.value)}><option value="all">All scenarios</option>{[...new Set(trials.map((row) => row.scenario))].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Network condition<select value={network} onChange={(event) => setNetwork(event.target.value)}><option value="all">All conditions</option><option value="nominal">Nominal (zero loss/jitter)</option><option value="degraded">Loss or jitter injected</option></select></label>
        <div><span>Visible independent trials</span><strong>{filtered.length}</strong><small>{summary.trial_counts.failed} runner failures in complete dataset</small></div>
      </div>
    </Panel>
    <div className="metric-grid">
      {[['Accuracy', accuracy], ['Precision', precision], ['Recall', recall], ['Specificity', specificity], ['F1', f1], ['False-positive rate', falsePositiveRate], ['False-negative rate', falseNegativeRate]].map(([label, value]) => <div className="metric" key={String(label)}><span>{label}</span><strong>{metric(value as number | null)}</strong></div>)}
    </div>
    <Panel title="Comparison by network condition" description="Classification accuracy for the selected scenario/loss/jitter groups; hover for trial count.">
      <div className="robustness-bars">{conditionGroups.map((group) => <div key={group.label} title={`${group.label}; n=${group.trials}`}><span><i style={{ width: `${group.accuracy * 100}%` }} /></span><strong>{metric(group.accuracy)}</strong><small>{group.label} · n={group.trials}</small></div>)}</div>
    </Panel>
    <div className="two-column">
      <Panel title="Event-level confusion matrix" description="Rows are injected truth; columns are production-detector predictions.">
        <div className="confusion-grid" aria-label="Event-level confusion matrix">
          <span /><strong>Predicted +</strong><strong>Predicted −</strong>
          <strong>Truth +</strong><div><span>TP</span><b>{counts.TP}</b></div><div><span>FN</span><b>{counts.FN}</b></div>
          <strong>Truth −</strong><div><span>FP</span><b>{counts.FP}</b></div><div><span>TN</span><b>{counts.TN}</b></div>
        </div>
      </Panel>
      <Panel title="Latency and network robustness" description="Confirmation/targeting are distinct from notification receipt.">
        <div className="trial-bars">{filtered.slice(0, 24).map((trial) => <div key={trial.trial_id} title={`${trial.trial_id}: ${trial.confirmation_latency_ms ?? "no confirmation"} ms`}><span style={{ height: `${Math.max(4, Math.min(100, (trial.confirmation_latency_ms ?? 0) / 18))}%` }} /><small>{trial.scenario.slice(0, 3)}</small></div>)}</div>
        <p className="evaluation-note">Target records are locally authoritative. Actual FCM notification receipt is <strong>not observed offline</strong> and is not inferred.</p>
      </Panel>
    </div>
    <Panel title="Independent trial records" description="Seeds and condition inputs are retained for exact reproduction."><div className="table-wrap"><table><thead><tr><th>Trial</th><th>Scenario</th><th>Seed</th><th>Truth</th><th>Prediction</th><th>Outcome</th><th>Loss</th><th>Jitter</th><th>Devices</th><th>Confirm ms</th><th>Target ms</th><th>Receipt</th></tr></thead><tbody>{filtered.map((trial) => <tr key={trial.trial_id}><td className="mono">{trial.trial_id}</td><td>{trial.scenario}</td><td>{trial.seed}</td><td>{trial.truth_positive ? "Positive" : "Negative"}</td><td>{trial.predicted_positive ? "Confirmed" : "Not confirmed"}</td><td><strong>{trial.outcome}</strong></td><td>{metric(trial.packet_loss_fraction)}</td><td>{trial.jitter_ms} ms</td><td>{trial.devices}</td><td>{trial.confirmation_latency_ms ?? "—"}</td><td>{trial.alert_target_latency_ms ?? "—"}</td><td>{trial.notification_receipt_status}</td></tr>)}</tbody></table></div></Panel>
  </div>;
}
