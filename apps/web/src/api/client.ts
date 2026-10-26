/**
 * The only place that talks to the API.
 *
 * Requests are same-origin and relative, so the browser adds the exact `Origin` header the
 * server checks and the session cookie travels without any CORS. The CSRF token lives in
 * memory only: it is never written to localStorage, sessionStorage or a cookie.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: string[];

  constructor(status: number, code: string, fields: string[] = []) {
    super(code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

const SAFE_METHODS = new Set(["GET", "HEAD"]);
const AUTH_PREFIX = "/api/v1/auth/";

let csrfToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

/** Called when a non-auth request is answered with 401, i.e. the session has ended. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

function toApiError(status: number, payload: unknown): ApiError {
  if (typeof payload === "object" && payload !== null) {
    const { error, fields } = payload as { error?: unknown; fields?: unknown };
    if (typeof error === "string") {
      const names = Array.isArray(fields)
        ? fields.filter((f): f is string => typeof f === "string")
        : [];
      return new ApiError(status, error, names);
    }
  }
  // Anything else (HTML error pages, stack traces...) is never shown to the user.
  return new ApiError(status, "unknown_error");
}

interface RequestOptions {
  /** A value sent as JSON. */
  body?: unknown;
  /** Text sent exactly as given (used for files the server must parse itself). */
  rawBody?: string;
  query?: Query;
  headers?: Record<string, string>;
  /** "blob" returns the response as a file instead of parsing JSON. */
  as?: "json" | "blob";
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const { body, rawBody, query, headers: extraHeaders, as = "json" } = options;
  const headers: Record<string, string> = { Accept: "application/json", ...extraHeaders };
  const hasBody = body !== undefined || rawBody !== undefined;
  if (hasBody) headers["Content-Type"] = "application/json";
  if (!SAFE_METHODS.has(method) && csrfToken !== null) headers["X-CSRF-Token"] = csrfToken;

  let response: Response;
  try {
    response = await fetch(withQuery(path, query), {
      method,
      headers,
      credentials: "same-origin",
      body: rawBody ?? (body === undefined ? undefined : JSON.stringify(body)),
    });
  } catch {
    throw new ApiError(0, "network_error");
  }

  if (response.ok && as === "blob") return (await response.blob()) as T;
  if (response.status === 204) return undefined as T;

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith(AUTH_PREFIX)) onUnauthorized?.();
    throw toApiError(response.status, payload);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  delete: <T>(path: string) => request<T>("DELETE", path),
  /** POST text exactly as it is (an import file), with optional query and headers. */
  postText: <T>(
    path: string,
    rawBody: string,
    options: { query?: Query; headers?: Record<string, string> } = {},
  ) => request<T>("POST", path, { rawBody, ...options }),
  /** Fetch a file (an export or a template) as a Blob. */
  getBlob: (path: string) => request<Blob>("GET", path, { as: "blob" }),
};
