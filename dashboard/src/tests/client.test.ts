import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiProblem, api } from "../api/client";

afterEach(() => {
  vi.restoreAllMocks();
  window.QUAKEMESH_CONFIG = undefined;
});

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

  it("adds the controlled demo key only to mutating AWS requests", async () => {
    window.QUAKEMESH_CONFIG = { apiKey: "demo-key" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      schema_version: "2.0",
      request_id: "request-3",
      data: { alert: {}, transition_created: true },
    }), { status: 200 }));
    await api.acknowledge("alert-1", "device-1");
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("x-api-key")).toBe("demo-key");
  });
});
