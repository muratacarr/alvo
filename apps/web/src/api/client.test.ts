import { describe, expect, it } from "vitest";

import { mockApi, failNetwork } from "../test/mockApi";
import { ApiError, api, getCsrfToken, setCsrfToken } from "./client";

describe("api client", () => {
  it("sends same-origin relative requests with cookies and no CSRF header on reads", async () => {
    const { calls } = mockApi({ "GET /api/v1/auth/me": { json: { user_id: "u", role: "user" } } });
    await api.get("/api/v1/auth/me");
    const [call] = calls;
    expect(call?.path).toBe("/api/v1/auth/me");
    expect(call?.credentials).toBe("same-origin");
    expect(call?.headers["x-csrf-token"]).toBeUndefined();
  });

  it("adds the CSRF token to every state-changing request", async () => {
    const { calls } = mockApi({
      "POST /api/v1/projects": { status: 201, json: {} },
      "PATCH /api/v1/projects/1": { json: {} },
      "DELETE /api/v1/projects/1": { status: 204 },
    });
    setCsrfToken("token-123");
    await api.post("/api/v1/projects", { title: "x" });
    await api.patch("/api/v1/projects/1", { title: "y" });
    await api.delete("/api/v1/projects/1");
    expect(calls.map((c) => c.headers["x-csrf-token"])).toEqual([
      "token-123",
      "token-123",
      "token-123",
    ]);
  });

  it("sends JSON bodies with a JSON content type and none on bodiless requests", async () => {
    const { calls } = mockApi({
      "POST /api/v1/projects": { status: 201, json: {} },
      "DELETE /api/v1/projects/1": { status: 204 },
    });
    await api.post("/api/v1/projects", { title: "x" });
    await api.delete("/api/v1/projects/1");
    expect(calls[0]?.headers["content-type"]).toBe("application/json");
    expect(calls[0]?.body).toEqual({ title: "x" });
    expect(calls[1]?.headers["content-type"]).toBeUndefined();
  });

  it("returns undefined for 204 responses", async () => {
    mockApi({ "DELETE /api/v1/projects/1": { status: 204 } });
    await expect(api.delete("/api/v1/projects/1")).resolves.toBeUndefined();
  });

  it("turns API errors into ApiError with status, code and failing fields", async () => {
    mockApi({
      "POST /api/v1/projects": {
        status: 422,
        json: { error: "invalid_request", fields: ["body.title"] },
      },
    });
    const error = await api.post("/api/v1/projects", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: "invalid_request", fields: ["body.title"] });
  });

  it("reports unexpected error bodies as a generic error without leaking them", async () => {
    mockApi({ "GET /api/v1/projects": { status: 500, json: { stack: "SECRET TRACE" } } });
    const error = (await api.get("/api/v1/projects").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("unknown_error");
    expect(error.message).not.toContain("SECRET");
  });

  it("maps network failures to a network_error", async () => {
    failNetwork();
    const error = (await api.get("/api/v1/projects").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, code: "network_error" });
  });

  it("keeps the CSRF token in memory only, never in browser storage", () => {
    setCsrfToken("in-memory-only");
    expect(getCsrfToken()).toBe("in-memory-only");
    expect(JSON.stringify({ ...localStorage })).not.toContain("in-memory-only");
    expect(JSON.stringify({ ...sessionStorage })).not.toContain("in-memory-only");
    expect(document.cookie).not.toContain("in-memory-only");
  });

  it("encodes query values", async () => {
    const { calls } = mockApi({ "GET /api/v1/projects": { json: { items: [], next_cursor: null } } });
    await api.get("/api/v1/projects", { limit: 20, cursor: "a b&c", include_archived: true });
    expect(calls[0]?.path).toBe("/api/v1/projects?limit=20&cursor=a+b%26c&include_archived=true");
  });
});
