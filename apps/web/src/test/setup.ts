import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { setCsrfToken } from "../api/client";

// axe probes canvas support; jsdom has none and only logs noise.
HTMLCanvasElement.prototype.getContext = () => null;

// Browser APIs Ant Design relies on that jsdom does not implement.
// Tests run as a user who prefers reduced motion: Ant Design then skips animations, which
// jsdom cannot finish (a closing dialog would otherwise stay in the document).
window.matchMedia = (query: string): MediaQueryList => ({
  matches: query.includes("prefers-reduced-motion"),
  media: query,
  onchange: null,
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
  addListener: () => undefined,
  removeListener: () => undefined,
  dispatchEvent: () => false,
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;

// jsdom logs "not implemented" for the pseudo-element form that Ant Design's click effect uses.
const originalGetComputedStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = (element: Element) => originalGetComputedStyle(element);

// jsdom has no object URLs (used for file downloads); tests spy on these.
URL.createObjectURL = () => "blob:jsdom";
URL.revokeObjectURL = () => undefined;

afterEach(() => {
  cleanup();
  setCsrfToken(null);
});
