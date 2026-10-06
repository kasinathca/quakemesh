import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiProblem, api } from "../api/client";

afterEach(() => vi.restoreAllMocks());

describe("V2 API client", () => {
  it("unwraps a versioned success envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      schema_version: "2.0",
      request_id: "request-1",
      data: { status: "ok", mode: "LOCAL", application_version: "1.0.1", stats: {} },
    }), { status: 200 }));
    const health = await api.health();
    expect(health.mode).toBe("LOCAL");
  });

  it("preserves stable machine error codes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      schema_version: "2.0",
      error: { code: "SCENARIO_ALREADY_RUNNING", message: "Active", request_id: "request-2", details: {} },
    }), { status: 409 }));
    await expect(api.start({ scenario: "isolated" })).rejects.toMatchObject({
      code: "SCENARIO_ALREADY_RUNNING",
      status: 409,
    } satisfies Partial<ApiProblem>);
  });
});
