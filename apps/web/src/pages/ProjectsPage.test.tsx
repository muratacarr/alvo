import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../test/a11y";
import { failNetwork, mockApi } from "../test/mockApi";
import { ME, project, renderWithProviders } from "../test/render";
import { ProjectsPage } from "./ProjectsPage";

const session = {
  "GET /api/v1/auth/me": { json: ME },
  "GET /api/v1/auth/csrf": { json: { csrf_token: "csrf-1" } },
};
const page = (items: unknown[], next_cursor: string | null = null) => ({
  json: { items, next_cursor },
});

function renderPage() {
  return renderWithProviders(<ProjectsPage />);
}

describe("ProjectsPage", () => {
  it("lists the user's projects", async () => {
    mockApi({
      ...session,
      "GET /api/v1/projects": page([
        project({ title: "HR Interview", description: "Soft skills" }),
        project({ id: "33333333-3333-4333-8333-333333333333", title: "Backend" }),
      ]),
    });
    renderPage();
    expect(await screen.findByText("HR Interview")).toBeInTheDocument();
    expect(screen.getByText("Soft skills")).toBeInTheDocument();
    expect(screen.getByText("Backend")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders project text as text, never as markup (XSS)", async () => {
    const payload = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>';
    mockApi({
      ...session,
      "GET /api/v1/projects": page([project({ title: payload, description: payload })]),
    });
    const { container } = renderPage();
    await screen.findAllByText(payload);
    expect(container.querySelector("img, script")).toBeNull();
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  });

  it("shows a loading state, then an empty state with guidance", async () => {
    mockApi({ ...session, "GET /api/v1/projects": page([]) });
    renderPage();
    expect(screen.getByRole("status")).toHaveTextContent("Loading projects");
    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
  });

  it("shows an error with a retry when the list cannot be loaded", async () => {
    mockApi({ ...session, "GET /api/v1/projects": { status: 500, json: { error: "internal_error" } } });
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load projects");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("says when the server cannot be reached", async () => {
    mockApi({ ...session, "GET /api/v1/projects": page([]) });
    renderPage();
    await screen.findByText(/No projects yet/);
    failNetwork();
    await userEvent.type(screen.getByLabelText("Title"), "Offline test");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("creates a project with the CSRF token and shows it in the list", async () => {
    const created = project({ id: "44444444-4444-4444-8444-444444444444", title: "New one" });
    let listed = false;
    const { calls } = mockApi({
      ...session,
      "GET /api/v1/projects": () => (listed ? page([created]) : page([])),
      "POST /api/v1/projects": () => {
        listed = true;
        return { status: 201, json: created };
      },
    });
    renderPage();
    await screen.findByText(/No projects yet/);
    await userEvent.type(screen.getByLabelText("Title"), "New one");
    await userEvent.type(screen.getByLabelText("Description (optional)"), "About it");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("New one")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ title: "New one", description: "About it" });
    expect(post?.headers["x-csrf-token"]).toBe("csrf-1");
    expect(screen.getByLabelText("Title")).toHaveValue("");
  });

  it("omits an empty description from the request", async () => {
    const { calls } = mockApi({
      ...session,
      "GET /api/v1/projects": page([]),
      "POST /api/v1/projects": { status: 201, json: project() },
    });
    renderPage();
    await userEvent.type(await screen.findByLabelText("Title"), "Only title{Enter}");
    await screen.findByRole("status");
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ title: "Only title" });
  });

  it("validates the title before sending anything", async () => {
    const { calls } = mockApi({ ...session, "GET /api/v1/projects": page([]) });
    renderPage();
    await userEvent.type(await screen.findByLabelText("Title"), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a title");
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
    expect(screen.getByLabelText("Title")).toHaveAttribute("aria-invalid", "true");
  });

  it("limits field lengths in the form", async () => {
    mockApi({ ...session, "GET /api/v1/projects": page([]) });
    renderPage();
    expect(await screen.findByLabelText("Title")).toHaveAttribute("maxlength", "200");
    expect(screen.getByLabelText("Description (optional)")).toHaveAttribute("maxlength", "2000");
  });

  it("shows a friendly message when the server rejects the input", async () => {
    mockApi({
      ...session,
      "GET /api/v1/projects": page([]),
      "POST /api/v1/projects": {
        status: 422,
        json: { error: "invalid_request", fields: ["body.title"] },
      },
    });
    renderPage();
    await userEvent.type(await screen.findByLabelText("Title"), "a\u0000b{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Check the highlighted fields");
  });

  it("archives a project and offers to restore it", async () => {
    let archived = false;
    const { calls } = mockApi({
      ...session,
      "GET /api/v1/projects": () => page(archived ? [] : [project()]),
      "DELETE /api/v1/projects/22222222-2222-4222-8222-222222222222": () => {
        archived = true;
        return { status: 204 };
      },
    });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Archive HR Interview" }));
    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "DELETE")?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("can show archived projects and restore one", async () => {
    let restored = false;
    const { calls } = mockApi({
      ...session,
      "GET /api/v1/projects": (call) =>
        call.path.includes("include_archived=true") && !restored
          ? page([project({ archived: true })])
          : page([project()]),
      "POST /api/v1/projects/22222222-2222-4222-8222-222222222222/unarchive": () => {
        restored = true;
        return { json: project() };
      },
    });
    renderPage();
    await userEvent.click(await screen.findByRole("checkbox", { name: "Show archived" }));
    const item = (await screen.findByText("Archived")).closest("li") as HTMLElement;
    await userEvent.click(within(item).getByRole("button", { name: "Restore HR Interview" }));
    expect(await screen.findByRole("button", { name: "Archive HR Interview" })).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/unarchive"))).toBe(true);
  });

  it("loads more with the server cursor", async () => {
    const { calls } = mockApi({
      ...session,
      "GET /api/v1/projects": (call) =>
        call.path.includes("cursor=next-1")
          ? page([project({ id: "55555555-5555-4555-8555-555555555555", title: "Second page" })])
          : page([project({ title: "First page" })], "next-1"),
    });
    renderPage();
    await screen.findByText("First page");
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("Second page")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
    expect(calls.filter((c) => c.method === "GET" && c.path.startsWith("/api/v1/projects"))).toHaveLength(2);
  });

  it("has no accessibility violations", async () => {
    mockApi({ ...session, "GET /api/v1/projects": page([project(), project({ archived: true, id: "6", title: "Old project" })]) });
    const { container } = renderPage();
    await screen.findByText("HR Interview");
    await expectNoA11yViolations(container);
  });

  it("is operable with the keyboard only", async () => {
    mockApi({
      ...session,
      "GET /api/v1/projects": page([]),
      "POST /api/v1/projects": { status: 201, json: project() },
    });
    renderPage();
    await screen.findByText(/No projects yet/);
    await userEvent.tab();
    expect(screen.getByLabelText("Title")).toHaveFocus();
    await userEvent.keyboard("Keyboard project{Enter}");
    expect(await screen.findByRole("status")).toBeInTheDocument();
  });
});
