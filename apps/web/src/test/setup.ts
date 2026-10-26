import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { setCsrfToken } from "../api/client";

// axe probes canvas support; jsdom has none and only logs noise.
HTMLCanvasElement.prototype.getContext = () => null;

afterEach(() => {
  cleanup();
  setCsrfToken(null);
});
