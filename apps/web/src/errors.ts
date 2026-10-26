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

const IMPORT_MESSAGES: Record<string, string> = {
  invalid_json: "The file is not valid JSON.",
  duplicate_key: "The file repeats a key inside one object. Remove the duplicate and try again.",
  too_deep: "The file is nested too deeply.",
  invalid_document: "The file does not match the import format. Compare it with the sample file.",
  schema_version_missing: "The file has no schemaVersion. Compare it with the sample file.",
  unsupported_schema_version:
    "The file uses an unsupported schemaVersion. Download the sample file to see the current format.",
  too_many_modules: "The file has too many modules.",
  too_many_topics: "The file has too many topics.",
  too_many_items: "The file has too many items. Split it into several files.",
  invalid_items: "Some items in the file are invalid.",
  payload_too_large: "The file is larger than 2 MiB, which is the import limit.",
  idempotency_key_reuse:
    "This import was already started with different settings. Choose the file again and retry.",
  archived: "This project is archived, so nothing can be imported.",
  rate_limited: "Too many imports in a short time. Wait a minute and try again.",
};

/** User-facing wording for import failures. */
export function describeImportError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const message = IMPORT_MESSAGES[error.code];
    if (message !== undefined) return message;
  }
  return describeError(error, fallback);
}
