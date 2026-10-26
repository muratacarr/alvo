import { vi } from "vitest";

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export interface RecordedCall {
  method: string;
  path: string;
  headers: Record<string, string>;
  body: unknown;
  rawBody: string | undefined;
  credentials: RequestCredentials | undefined;
}

export interface MockResponse {
  status?: number;
  json?: unknown;
}

export type Handler = MockResponse | ((call: RecordedCall) => MockResponse | Promise<MockResponse>);

/**
 * Replaces `fetch` with a router keyed by "METHOD /path". Requests nobody expects fail the
 * test loudly instead of silently returning something.
 */
export function mockApi(routes: Record<string, Handler>): { calls: RecordedCall[] } {
  const calls: RecordedCall[] = [];
  const impl = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    const headers = Object.fromEntries(new Headers(init?.headers).entries());
    const call: RecordedCall = {
      method,
      path: url,
      headers,
      body: typeof init?.body === "string" ? safeJson(init.body) : undefined,
      rawBody: typeof init?.body === "string" ? init.body : undefined,
      credentials: init?.credentials,
    };
    calls.push(call);
    const route = routes[`${method} ${url.split("?")[0]}`];
    if (route === undefined) {
      throw new Error(`Unexpected request in test: ${method} ${url}`);
    }
    const result = typeof route === "function" ? await route(call) : route;
    const status = result.status ?? 200;
    const noBody = status === 204 || result.json === undefined;
    return new Response(noBody ? null : JSON.stringify(result.json), {
      status,
      headers: noBody ? {} : { "Content-Type": "application/json" },
    });
  };
  vi.stubGlobal("fetch", vi.fn(impl));
  return { calls };
}

export const ME = { user_id: "11111111-1111-4111-8111-111111111111", role: "user" };

/**
 * Anonymous until the sign-in request succeeds, then the session endpoint reports the user.
 * Optionally waits on `gate` before answering the sign-in request.
 */
export function loginFlow(csrf = "csrf-abc", gate?: Promise<void>): Record<string, Handler> {
  let signedIn = false;
  return {
    "GET /api/v1/auth/me": () =>
      signedIn ? { json: ME } : { status: 401, json: { error: "unauthenticated" } },
    "POST /api/v1/auth/dev-login": async () => {
      await gate;
      signedIn = true;
      return { json: { user_id: ME.user_id, csrf_token: csrf } };
    },
  };
}

export function failNetwork(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }),
  );
}
