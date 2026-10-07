import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DataState } from "../components/DataState";
import { Layout } from "../components/Layout";
import { StatusBadge } from "../components/StatusBadge";

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
});
