import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { setCsrfToken } from "../api/client";

// axe probes canvas support; jsdom has none and only logs noise.
HTMLCanvasElement.prototype.getContext = () => null;

// Browser APIs Ant Design relies on that jsdom does not implement.
window.matchMedia = (query: string): MediaQueryList => ({
  matches: false,
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

afterEach(() => {
  cleanup();
  setCsrfToken(null);
});
