import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DataState } from "../components/DataState";
import { Layout } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";
import { EvaluationView } from "../features/evaluation/EvaluationView";

describe("operations components", () => {
  it("renders unavailable data explicitly", () => {
    render(<DataState />);
    expect(screen.getByText("Waiting for data")).toBeInTheDocument();
  });

  it("renders semantic status text without color-only meaning", () => {
    render(<StatusBadge value="ACKNOWLEDGED" />);
    expect(screen.getByText("ACKNOWLEDGED")).toHaveClass("status-acknowledged");
  });

  it("shows the real configured cloud environment and region", () => {
    render(<Layout active="overview" onNavigate={() => undefined} connection="connected" lastUpdated={null} error={null} environmentLabel="AWS V2 Demo" region="ap-south-1"><div>Cloud data</div></Layout>);
    expect(screen.getByText("AWS V2 Demo · ap-south-1")).toBeInTheDocument();
  });

  it("labels evaluation data as offline synthetic and never implies notification receipt", async () => {
    const summary = { result_kind: "OFFLINE_SYNTHETIC_SIMULATION_EVALUATION", disclaimer: "Not real-world earthquake-detection accuracy.", generated_at: "2026-10-19T00:00:00Z", trial_counts: { requested: 1, completed: 1, failed: 0 }, reproducibility: { geo_index: "h3-py (real H3)", detector: {} } };
    const trials = [{ trial_id: "distributed-001", scenario: "distributed", seed: 7, truth_positive: true, predicted_positive: true, outcome: "TP", packet_loss_fraction: 0, jitter_ms: 0, devices: 12, confirmation_latency_ms: 240, alert_target_latency_ms: 240, transport_delivery_success_ratio: 1, notification_receipt_status: "NOT_OBSERVED_OFFLINE", failure: null }];
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => Promise.resolve(new Response(JSON.stringify(String(input).includes("trials.json") ? trials : summary))));
    render(<EvaluationView />);
    expect(await screen.findByText(/OFFLINE SYNTHETIC SIMULATION EVALUATION/i)).toBeInTheDocument();
    expect(screen.getByText(/FCM receipt remains distinct from SNS acceptance/)).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
