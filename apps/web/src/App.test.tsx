import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { getCsrfToken } from "./api/client";
import { expectNoA11yViolations } from "./test/a11y";
import { failNetwork, loginFlow, mockApi } from "./test/mockApi";
import { ME, project, renderWithProviders } from "./test/render";

const signedIn = {
  "GET /api/v1/auth/me": { json: ME },
  "GET /api/v1/auth/csrf": { json: { csrf_token: "csrf-1" } },
  "GET /api/v1/projects": { json: { items: [project()], next_cursor: null } },
};

describe("App", () => {
  it("sends anonymous visitors to the sign-in page", async () => {
    mockApi({ "GET /api/v1/auth/me": { status: 401, json: { error: "unauthenticated" } } });
    renderWithProviders(<App />, "/");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("restores an existing session and shows the projects", async () => {
    mockApi(signedIn);
    renderWithProviders(<App />, "/");
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(await screen.findByText("HR Interview")).toBeInTheDocument();
    expect(getCsrfToken()).toBe("csrf-1");
  });

  it("shows a loading state while the session is being checked", () => {
    mockApi(signedIn);
    renderWithProviders(<App />, "/");
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  it("signs in from the login page and lands on the projects", async () => {
    mockApi({
      ...loginFlow("csrf-9"),
      "GET /api/v1/projects": { json: { items: [], next_cursor: null } },
    });
    renderWithProviders(<App />, "/");
    await userEvent.type(await screen.findByLabelText("Development user name"), "alice{Enter}");
    expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(getCsrfToken()).toBe("csrf-9");
  });

  it("signs out, clears the CSRF token and returns to sign-in", async () => {
    let signedOut = false;
    const { calls } = mockApi({
      ...signedIn,
      "GET /api/v1/auth/me": () =>
        signedOut ? { status: 401, json: { error: "unauthenticated" } } : { json: ME },
      "POST /api/v1/auth/logout": () => {
        signedOut = true;
        return { status: 204 };
      },
    });
    renderWithProviders(<App />, "/");
    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(getCsrfToken()).toBeNull();
    expect(calls.find((c) => c.path.endsWith("/logout"))?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("returns to sign-in when the session expires during use", async () => {
    mockApi({
      ...signedIn,
      "GET /api/v1/projects": { status: 401, json: { error: "unauthenticated" } },
    });
    renderWithProviders(<App />, "/");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("explains when the server cannot be reached at start-up", async () => {
    failNetwork();
    renderWithProviders(<App />, "/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("has a skip link, landmarks and shows the signed-in role", async () => {
    mockApi(signedIn);
    const { container } = renderWithProviders(<App />, "/");
    await screen.findByText("HR Interview");
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(screen.getByText(/Signed in as user/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("opens a project at its own address", async () => {
    const id = "22222222-2222-4222-8222-222222222222";
    mockApi({
      ...signedIn,
      [`GET /api/v1/projects/${id}`]: { json: project({ id, title: "Deep linked" }) },
      [`GET /api/v1/projects/${id}/modules`]: { json: { items: [], next_cursor: null } },
      [`GET /api/v1/projects/${id}/topics`]: { json: { items: [], next_cursor: null } },
    });
    renderWithProviders(<App />, `/projects/${id}`);
    expect(await screen.findByRole("heading", { name: "Deep linked" })).toBeInTheDocument();
  });

  it("shows a helpful page for unknown addresses", async () => {
    mockApi(signedIn);
    renderWithProviders(<App />, "/no/such/page");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to projects" })).toHaveAttribute("href", "/");
  });

  it("never writes session data to browser storage", async () => {
    mockApi(signedIn);
    renderWithProviders(<App />, "/");
    await screen.findByText("HR Interview");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});

/** Removes `@layer antd { ... }` and `@keyframes ... { ... }` blocks, matching braces. */
function withoutLayerAndKeyframes(css: string): string {
  let result = "";
  let index = 0;
  while (index < css.length) {
    const rest = css.slice(index);
    const match = /^@(layer antd|keyframes[^{]*)\{/.exec(rest);
    if (!match) {
      result += css.charAt(index);
      index += 1;
      continue;
    }
    let depth = 1;
    index += match[0].length;
    while (index < css.length && depth > 0) {
      depth += css.charAt(index) === "{" ? 1 : css.charAt(index) === "}" ? -1 : 0;
      index += 1;
    }
  }
  return result;
}

function injectedCss(): string {
  return Array.from(document.head.querySelectorAll("style"))
    .map((style) => style.textContent ?? "")
    .join(" ");
}

describe("Ant Design styling", () => {
  it("puts component styles in the antd cascade layer so Tailwind cannot override them", async () => {
    mockApi({ "GET /api/v1/auth/me": { status: 401, json: { error: "unauthenticated" } } });
    renderWithProviders(<App />, "/");
    await screen.findByRole("heading", { name: "Sign in" });
    const css = injectedCss();
    expect(css).toContain("@layer antd");
    // Rules outside a layer beat every layer. Only custom-property definitions may live there.
    const unlayered = withoutLayerAndKeyframes(css);
    const properties = [...unlayered.matchAll(/[{;]\s*([a-z-]+)\s*:/gi)].map((m) => m[1] ?? "");
    const visual = properties.filter((name) => !name.startsWith("--"));
    expect(visual).toEqual([]);
  });

  it("does not load fonts or styles from other hosts", async () => {
    mockApi({ "GET /api/v1/auth/me": { status: 401, json: { error: "unauthenticated" } } });
    renderWithProviders(<App />, "/");
    await screen.findByRole("heading", { name: "Sign in" });
    expect(injectedCss()).not.toMatch(/https?:\/\//);
    expect(document.head.querySelector("link[href^='http']")).toBeNull();
  });
});
