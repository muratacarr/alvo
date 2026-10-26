import { randomUUID } from "node:crypto";

import { expect, type Page } from "@playwright/test";

/** A fresh user name per test run, so runs never see each other's data. */
export function newUserName(prefix = "e2e"): string {
  return `${prefix}-${randomUUID().slice(0, 8)}`;
}

export async function signIn(page: Page, name: string): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Development user name").fill(name);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Projects", level: 1 })).toBeVisible();
}

export async function createProject(page: Page, title: string): Promise<void> {
  await page.getByLabel("Title").fill(title);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("link", { name: title })).toBeVisible();
}

/** Opens a project, adds a module, a topic and one item, and selects the topic. */
export async function buildSmallProject(page: Page, title: string): Promise<void> {
  await createProject(page, title);
  await page.getByRole("link", { name: title }).click();
  await page.getByLabel("New module title").fill("Core");
  await page.getByLabel("New module title").press("Enter");
  await expect(page.getByText("Core", { exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Module for the new topic" }).click();
  await page.getByRole("option", { name: "Core" }).click();
  // Wait for the list to finish closing so later checks never see it half open.
  await expect(page.locator(".ant-select-dropdown")).toBeHidden();
  await page.getByLabel("New topic title").fill("Dependency injection");
  await page.getByLabel("New topic title").press("Enter");
  await page.getByText("Dependency injection", { exact: true }).click();
  await page.getByRole("button", { name: "Add item" }).click();
  const dialog = page.getByRole("dialog", { name: "Add item" });
  await dialog.getByLabel("Prompt").fill("What is dependency injection?");
  await dialog.getByRole("button", { name: "Save item" }).click();
  await expect(page.getByText("What is dependency injection?")).toBeVisible();
}
