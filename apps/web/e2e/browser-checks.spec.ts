import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { buildSmallProject, newUserName, signIn } from "./helpers";

const require = createRequire(import.meta.url);

const MOBILE = { width: 375, height: 667 };

interface AxeResult {
  violations: { id: string; help: string; nodes: { target: unknown[] }[] }[];
}

/** Every screen worth checking, reached the way a user would reach it. */
async function visitScreens(page: Page, visit: (label: string) => Promise<void>): Promise<void> {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await visit("sign-in");
  await signIn(page, newUserName());
  await visit("projects");
  await buildSmallProject(page, "Layout check");
  await visit("project detail");
  await page.getByRole("button", { name: "Add item" }).click();
  await expect(page.getByRole("dialog", { name: "Add item" })).toBeVisible();
  await visit("add item dialog");
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.getByRole("link", { name: "Import and export" }).click();
  await expect(page.getByRole("heading", { name: "Import and export" })).toBeVisible();
  await visit("import");
  const sample = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download sample file" }).click();
  await page.getByLabel("Import file (JSON)").setInputFiles(await (await sample).path());
  await page.getByRole("button", { name: "Preview import" }).click();
  await expect(page.getByRole("region", { name: "Preview" })).toBeVisible();
  await visit("import preview");
}

test("the strict Content-Security-Policy is never violated on any screen", async ({ browser }) => {
  // No bypassCSP here: the browser enforces the policy the server sends.
  const context = await browser.newContext();
  const page = await context.newPage();
  const problems: string[] = [];
  page.on("console", (message) => {
    const text = message.text();
    // The first "who am I?" call before signing in gets a normal 401.
    if (message.type() === "error" && !text.includes("status of 401")) problems.push(text);
  });
  page.on("pageerror", (error) => problems.push(error.message));
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  await visitScreens(page, async () => undefined);
  expect(problems).toEqual([]);
  await context.close();
});

async function runAxe(browser: Browser): Promise<string[]> {
  // axe is injected as an inline script, which the strict policy rightly blocks; this context
  // lets the test tool in without changing the policy the real pages are served with.
  const context = await browser.newContext({ bypassCSP: true });
  const page = await context.newPage();
  const source = await readFile(require.resolve("axe-core/axe.min.js"), "utf8");
  const found: string[] = [];
  await visitScreens(page, async (label) => {
    await page.addScriptTag({ content: source });
    const result = await page.evaluate(() =>
      (window as unknown as { axe: { run: (c: Document) => Promise<AxeResult> } }).axe.run(document),
    );
    for (const violation of result.violations) {
      const targets = JSON.stringify(violation.nodes.map((node) => node.target));
      found.push(`${label}: ${violation.id} (${violation.help}) ${targets}`);
    }
  });
  await context.close();
  return found;
}

test("real layout has no accessibility violations, including color contrast", async ({ browser }) => {
  expect(await runAxe(browser)).toEqual([]);
});

test("on a phone-sized screen nothing is cut off or scrolls sideways", async ({ browser }) => {
  const context = await browser.newContext({ viewport: MOBILE });
  const page = await context.newPage();
  const wide: string[] = [];
  await visitScreens(page, async (label) => {
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    if (overflow > 0) wide.push(`${label}: ${overflow}px too wide`);
  });
  expect(wide).toEqual([]);
  await context.close();
});

test("the app is installable and the service worker never stores API data", async ({ page }) => {
  await signIn(page, newUserName());
  await buildSmallProject(page, "Cache check");

  const manifest = await page.request.get("/manifest.webmanifest");
  expect(manifest.ok()).toBe(true);
  const { icons } = (await manifest.json()) as { icons: { src: string }[] };
  for (const icon of icons) expect((await page.request.get(icon.src)).ok()).toBe(true);

  await page.evaluate(() => navigator.serviceWorker.ready);
  // Reload so the page is controlled by the worker and its requests pass through it.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Cache check", level: 1 })).toBeVisible();

  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      for (const request of await cache.keys()) urls.push(new URL(request.url).pathname);
    }
    return urls;
  });
  expect(cached.length).toBeGreaterThan(0);
  expect(cached.filter((path) => path.startsWith("/api/"))).toEqual([]);
});
