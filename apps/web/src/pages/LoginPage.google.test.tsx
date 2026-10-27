import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../test/a11y";
import { mockApi } from "../test/mockApi";

// The production build hides the development form (VITE_DEV_LOGIN=false) and shows Google.
// The switch is read when the module loads, so the page is imported after setting it.
async function renderLogin(path = "/login") {
  vi.stubEnv("VITE_DEV_LOGIN", "false");
  vi.resetModules();
  // Imported after the reset so the page and the providers share one copy of the auth context.
  const { LoginPage } = await import("./LoginPage");
  const { renderWithProviders } = await import("../test/render");
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<p>Home</p>} />
    </Routes>,
    path,
  );
}

const anonymous = { "GET /api/v1/auth/me": { status: 401, json: { error: "unauthenticated" } } };

describe("LoginPage in a production build", () => {
  beforeEach(() => {
    mockApi(anonymous);
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("offers Google sign-in as a plain link to the API and hides the development form", async () => {
    const { container } = await renderLogin();
    const link = await screen.findByRole("link", { name: "Sign in with Google" });
    expect(link).toHaveAttribute("href", "/api/v1/auth/google/start");
    expect(screen.queryByLabelText("Development user name")).not.toBeInTheDocument();
    expect(screen.getByText(/invitation only/i)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("explains an uninvited account", async () => {
    await renderLogin("/login?signin=not_invited");
    expect(await screen.findByRole("alert")).toHaveTextContent("has not been invited");
  });

  it("shows a generic message when sign-in did not complete", async () => {
    await renderLogin("/login?signin=failed");
    expect(await screen.findByRole("alert")).toHaveTextContent("did not complete");
  });

  it("never shows text taken from the address bar", async () => {
    await renderLogin("/login?signin=%3Cb%3Ehacked%3C%2Fb%3E");
    await screen.findByRole("link", { name: "Sign in with Google" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/hacked/)).not.toBeInTheDocument();
  });
});
