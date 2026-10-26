import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { buildSmallProject, newUserName, signIn } from "./helpers";

test("a user builds a project, exports it, imports a file and cannot be seen by another user", async ({
  page,
  browser,
}) => {
  await signIn(page, newUserName("alice"));
  await buildSmallProject(page, "E2E interview");
  const projectUrl = page.url().split("?")[0] ?? "";

  await page.getByRole("link", { name: "Import and export" }).click();
  await expect(page.getByRole("heading", { name: "Import and export" })).toBeVisible();

  // The export contains what was just created.
  const exportDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export this project" }).click();
  const exported = await exportDownload;
  expect(exported.suggestedFilename()).toBe("alvo-export.json");
  expect(await readFile(await exported.path(), "utf8")).toContain("What is dependency injection?");

  // The sample file downloaded from the app can be imported back.
  const sampleDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download sample file" }).click();
  const samplePath = await (await sampleDownload).path();

  await page.getByLabel("Import file (JSON)").setInputFiles(samplePath);
  await page.getByRole("button", { name: "Preview import" }).click();
  await expect(page.getByRole("region", { name: "Preview" })).toBeVisible();
  await page.getByRole("button", { name: /^Import \d+ new items?$/ }).click();
  await expect(page.getByRole("status").filter({ hasText: /Imported \d+ new item/ })).toBeVisible();

  // Importing the same file again finds nothing new (no duplicates).
  await page.getByLabel("Import file (JSON)").setInputFiles(samplePath);
  await page.getByRole("button", { name: "Preview import" }).click();
  await expect(page.getByText(/Nothing new to import/)).toBeVisible();

  // The project still shows the first module.
  await page.getByRole("link", { name: "E2E interview" }).click();
  await expect(page.getByText("Core", { exact: true })).toBeVisible();

  // Another user gets the same answer as for a project that does not exist.
  const context = await browser.newContext();
  const other = await context.newPage();
  await signIn(other, newUserName("bob"));
  await other.goto(projectUrl);
  await expect(other.getByRole("heading", { name: "Project not found" })).toBeVisible();
  await context.close();
});
