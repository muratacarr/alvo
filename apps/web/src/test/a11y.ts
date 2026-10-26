import axe from "axe-core";
import { expect } from "vitest";

/**
 * Runs axe-core on rendered markup. jsdom has no layout, so the colour-contrast rule cannot
 * be evaluated here; contrast is checked in a real browser (Playwright, later slice).
 */
export async function expectNoA11yViolations(container: Element): Promise<void> {
  const results = await axe.run(container, {
    rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
  });
  const summary = results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
  expect(summary).toEqual([]);
}
