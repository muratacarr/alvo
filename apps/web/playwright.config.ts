import { defineConfig } from "@playwright/test";

// These tests drive the real application: the compose stack must be running
// (see docs/ops/local-development.md). Locally set PW_CHANNEL=chrome to use the installed Chrome;
// CI installs Playwright's own Chromium.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    channel: process.env.PW_CHANNEL || undefined,
    // Nothing is recorded: pages contain the signed-in user's data.
    trace: "off",
    screenshot: "off",
    video: "off",
  },
});
