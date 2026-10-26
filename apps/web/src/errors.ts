import { ApiError } from "./api/client";

/** User-facing wording for failures. Server details are never shown. */
export function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.code === "network_error") {
      return "Cannot reach the server. Check your connection and try again.";
    }
    if (error.code === "invalid_request") {
      return "Check the highlighted fields and try again.";
    }
  }
  return fallback;
}
