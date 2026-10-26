import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";

import { getCsrfToken } from "../api/client";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../test/a11y";
import { failNetwork, loginFlow, mockApi } from "../test/mockApi";
import { renderWithProviders } from "../test/render";
import { LoginPage } from "./LoginPage";

function renderLogin() {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<p>Home</p>} />
    </Routes>,
    "/login",
  );
}

const anonymous = { "GET /api/v1/auth/me": { status: 401, json: { error: "unauthenticated" } } };

describe("LoginPage", () => {
  it("has a labelled field, a submit button and no accessibility violations", async () => {
    mockApi(anonymous);
    const { container } = renderLogin();
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByLabelText("Development user name")).toBeRequired();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
    await expectNoA11yViolations(container);
  });

  it("does not send a request when the name is empty and tells the user", async () => {
    const { calls } = mockApi(anonymous);
    renderLogin();
    await userEvent.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a user name");
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("signs in, keeps the CSRF token for later requests and leaves the login page", async () => {
    const { calls } = mockApi({
      ...loginFlow("csrf-abc"),
      "GET /api/v1/auth/csrf": { json: { csrf_token: "csrf-abc" } },
    });
    renderLogin();
    await userEvent.type(await screen.findByLabelText("Development user name"), "alice{Enter}");
    expect(await screen.findByText("Home")).toBeInTheDocument();
    const login = calls.find((c) => c.method === "POST");
    expect(login?.body).toEqual({ subject: "alice" });
    expect(getCsrfToken()).toBe("csrf-abc");
  });

  it("explains that sign-in is unavailable when the server has no login route", async () => {
    mockApi({ ...anonymous, "POST /api/v1/auth/dev-login": { status: 404, json: { error: "not_found" } } });
    renderLogin();
    await userEvent.type(await screen.findByLabelText("Development user name"), "alice");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign-in is not available");
  });

  it("shows a generic error when the request is rejected", async () => {
    mockApi({ ...anonymous, "POST /api/v1/auth/dev-login": { status: 403, json: { error: "forbidden" } } });
    renderLogin();
    await userEvent.type(await screen.findByLabelText("Development user name"), "alice");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not sign in");
    expect(alert).not.toHaveTextContent("forbidden");
  });

  it("says when the server cannot be reached", async () => {
    mockApi(anonymous);
    renderLogin();
    await screen.findByRole("heading", { name: "Sign in" });
    failNetwork();
    await userEvent.type(screen.getByLabelText("Development user name"), "alice");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("disables the button while signing in to prevent double submits", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    mockApi(loginFlow("t", gate));
    renderLogin();
    await userEvent.type(await screen.findByLabelText("Development user name"), "alice");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled());
    release();
    expect(await screen.findByText("Home")).toBeInTheDocument();
  });

  it("limits the length of the name field", async () => {
    mockApi(anonymous);
    renderLogin();
    expect(await screen.findByLabelText("Development user name")).toHaveAttribute("maxlength", "200");
  });
});
