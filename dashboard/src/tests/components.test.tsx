import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DataState } from "../components/DataState";
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
});
