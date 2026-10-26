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
    if (error.code === "duplicate") {
      return "An item with the same type and prompt already exists in this project.";
    }
    if (error.code === "archived") {
      return "The project or topic is archived, so it cannot be changed.";
    }
  }
  return fallback;
}
