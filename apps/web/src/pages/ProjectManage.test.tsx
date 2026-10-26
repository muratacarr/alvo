import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../test/a11y";
import { failNetwork, mockApi, type Handler } from "../test/mockApi";
import { ME, project, renderWithProviders } from "../test/render";
import { ProjectDetailPage } from "./ProjectDetailPage";

const PID = "22222222-2222-4222-8222-222222222222";
const BASE = `/api/v1/projects/${PID}`;
const M1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1";
const M2 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2";
const T1 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1";
const T2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2";
const I1 = "cccccccc-cccc-4ccc-8ccc-ccccccccccc1";

const stamp = { created_at: "2026-01-01T12:00:00Z", updated_at: "2026-01-01T12:00:00Z" };
const module_ = (id: string, title: string) => ({ id, project_id: PID, title, archived: false, ...stamp });
const topic = (id: string, module_id: string, title: string) => ({
  id,
  project_id: PID,
  module_id,
  title,
  archived: false,
  ...stamp,
});
const item = {
  id: I1,
  project_id: PID,
  topic_id: T1,
  type: "question",
  prompt: "What is dependency injection?",
  sample_answer: null,
  translation: null,
  keywords: [],
  tags: [],
  follow_up_questions: [],
  difficulty: null,
  external_id: null,
  practice_modes: [],
  archived: false,
  ...stamp,
};
const page = (items: unknown[]) => ({ json: { items, next_cursor: null } });

const session = {
  "GET /api/v1/auth/me": { json: ME },
  "GET /api/v1/auth/csrf": { json: { csrf_token: "csrf-1" } },
};

function routes(extra: Record<string, Handler> = {}): Record<string, Handler> {
  return {
    ...session,
    [`GET ${BASE}`]: { json: project({ id: PID, title: "Backend Interview" }) },
    [`GET ${BASE}/modules`]: page([module_(M1, "Technical"), module_(M2, "Behavioural")]),
    [`GET ${BASE}/topics`]: page([topic(T1, M1, "Dependency Injection"), topic(T2, M2, "Teamwork")]),
    [`GET ${BASE}/items`]: page([item]),
    ...extra,
  };
}

function renderDetail(path = `/projects/${PID}`) {
  return renderWithProviders(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
    </Routes>,
    path,
  );
}

async function openManager() {
  await userEvent.click(await screen.findByRole("button", { name: "Manage modules and topics" }));
}

describe("managing modules and topics", () => {
  it("keeps the management tools out of the way until asked for", async () => {
    mockApi(routes());
    renderDetail();
    const toggle = await screen.findByRole("button", { name: "Manage modules and topics" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Rename module Technical" })).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Rename module Technical" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive topic Teamwork" })).toBeInTheDocument();
  });

  it("renames a module and sends only the title", async () => {
    let title = "Technical";
    const { calls } = mockApi(
      routes({
        [`GET ${BASE}/modules`]: () => page([module_(M1, title), module_(M2, "Behavioural")]),
        [`PATCH ${BASE}/modules/${M1}`]: (call) => {
          title = (call.body as { title: string }).title;
          return { json: module_(M1, title) };
        },
      }),
    );
    renderDetail();
    await openManager();
    await userEvent.click(screen.getByRole("button", { name: "Rename module Technical" }));
    const dialog = await screen.findByRole("dialog", { name: "Rename module" });
    const input = within(dialog).getByLabelText("New name");
    expect(input).toHaveValue("Technical");
    await userEvent.clear(input);
    await userEvent.type(input, "Engineering");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toEqual({ title: "Engineering" });
    expect(patch?.headers["x-csrf-token"]).toBe("csrf-1");
    expect(await screen.findByRole("button", { name: "Rename module Engineering" })).toBeInTheDocument();
  });

  it("renames a topic", async () => {
    const { calls } = mockApi(
      routes({ [`PATCH ${BASE}/topics/${T2}`]: { json: topic(T2, M2, "Collaboration") } }),
    );
    renderDetail();
    await openManager();
    await userEvent.click(screen.getByRole("button", { name: "Rename topic Teamwork" }));
    const dialog = await screen.findByRole("dialog", { name: "Rename topic" });
    const input = within(dialog).getByLabelText("New name");
    await userEvent.clear(input);
    await userEvent.type(input, "Collaboration");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ title: "Collaboration" });
  });

  it("does not call the server when the name is unchanged, and rejects an empty name", async () => {
    const { calls } = mockApi(routes());
    renderDetail();
    await openManager();
    await userEvent.click(screen.getByRole("button", { name: "Rename module Technical" }));
    const dialog = await screen.findByRole("dialog", { name: "Rename module" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "Rename module Technical" }));
    const again = await screen.findByRole("dialog", { name: "Rename module" });
    await userEvent.clear(within(again).getByLabelText("New name"));
    await userEvent.click(within(again).getByRole("button", { name: "Save" }));
    expect(await within(again).findByText("Enter a name.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([]);
  });

  it("limits the name length and keeps the dialog open on failures", async () => {
    mockApi(routes({ [`PATCH ${BASE}/modules/${M1}`]: { status: 409, json: { error: "archived" } } }));
    renderDetail();
    await openManager();
    await userEvent.click(screen.getByRole("button", { name: "Rename module Technical" }));
    const dialog = await screen.findByRole("dialog", { name: "Rename module" });
    const input = within(dialog).getByLabelText("New name");
    expect(input).toHaveAttribute("maxlength", "200");
    await userEvent.type(input, "!");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("archived");
    failNetwork();
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent("Cannot reach the server"));
  });

  it("asks before archiving a module and explains what happens", async () => {
    let archived = false;
    const { calls } = mockApi(
      routes({
        [`GET ${BASE}/modules`]: () =>
          page(archived ? [module_(M2, "Behavioural")] : [module_(M1, "Technical"), module_(M2, "Behavioural")]),
        [`DELETE ${BASE}/modules/${M1}`]: () => {
          archived = true;
          return { status: 204 };
        },
      }),
    );
    renderDetail();
    await openManager();
    await userEvent.click(screen.getByRole("button", { name: "Archive module Technical" }));
    const dialog = await screen.findByRole("dialog", { name: "Archive module" });
    expect(within(dialog).getByText(/Technical/)).toBeInTheDocument();
    expect(within(dialog).getByText(/topics and items/)).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "DELETE")).toEqual([]);
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Rename module Technical" })).not.toBeInTheDocument());
    expect(calls.find((c) => c.method === "DELETE")?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("does nothing when archiving is cancelled", async () => {
    const { calls } = mockApi(routes());
    renderDetail();
    await openManager();
    await userEvent.click(screen.getByRole("button", { name: "Archive topic Teamwork" }));
    const dialog = await screen.findByRole("dialog", { name: "Archive topic" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.filter((c) => c.method === "DELETE")).toEqual([]);
  });

  it("leaves the topic view when the open topic is archived", async () => {
    let archived = false;
    mockApi(
      routes({
        [`GET ${BASE}/topics`]: () =>
          page(archived ? [topic(T2, M2, "Teamwork")] : [topic(T1, M1, "Dependency Injection"), topic(T2, M2, "Teamwork")]),
        [`DELETE ${BASE}/topics/${T1}`]: () => {
          archived = true;
          return { status: 204 };
        },
      }),
    );
    renderDetail(`/projects/${PID}?topic=${T1}`);
    await screen.findByText("What is dependency injection?");
    await openManager();
    await userEvent.click(screen.getByRole("button", { name: "Archive topic Dependency Injection" }));
    const dialog = await screen.findByRole("dialog", { name: "Archive topic" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));
    expect(await screen.findByText(/Select a topic/)).toBeInTheDocument();
  });

  it("offers no management tools for an archived project", async () => {
    mockApi(routes({ [`GET ${BASE}`]: { json: project({ id: PID, title: "Old", archived: true }) } }));
    renderDetail();
    await screen.findByText(/This project is archived/);
    expect(screen.queryByRole("button", { name: "Manage modules and topics" })).not.toBeInTheDocument();
  });

  it("has no accessibility violations with the tools open", async () => {
    mockApi(routes());
    const { container } = renderDetail();
    await openManager();
    await expectNoA11yViolations(container);
  });
});

describe("moving an item to another topic", () => {
  const withTopic = `/projects/${PID}?topic=${T1}`;

  it("offers every other topic, with its module, and sends only the new topic", async () => {
    const { calls } = mockApi(routes({ [`PATCH ${BASE}/items/${I1}`]: { json: { ...item, topic_id: T2 } } }));
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Move What is dependency injection?" }));
    const dialog = await screen.findByRole("dialog", { name: "Move item" });
    await userEvent.click(within(dialog).getByRole("combobox", { name: "Move to topic" }));
    expect(screen.queryByRole("option", { name: "Technical › Dependency Injection" })).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("option", { name: "Behavioural › Teamwork" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Move" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toEqual({ topic_id: T2 });
    expect(patch?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("asks for a target before moving", async () => {
    const { calls } = mockApi(routes());
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Move What is dependency injection?" }));
    const dialog = await screen.findByRole("dialog", { name: "Move item" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Move" }));
    expect(await within(dialog).findByText("Choose a topic.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([]);
  });

  it("explains a duplicate in the target topic", async () => {
    mockApi(routes({ [`PATCH ${BASE}/items/${I1}`]: { status: 409, json: { error: "duplicate" } } }));
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Move What is dependency injection?" }));
    const dialog = await screen.findByRole("dialog", { name: "Move item" });
    await userEvent.click(within(dialog).getByRole("combobox", { name: "Move to topic" }));
    await userEvent.click(await screen.findByRole("option", { name: "Behavioural › Teamwork" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Move" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("already exists in this project");
  });

  it("has no move action when there is no other topic or the project is archived", async () => {
    mockApi(routes({ [`GET ${BASE}/topics`]: page([topic(T1, M1, "Dependency Injection")]) }));
    renderDetail(withTopic);
    await screen.findByText("What is dependency injection?");
    expect(screen.queryByRole("button", { name: /^Move / })).not.toBeInTheDocument();
  });

  it("has no accessibility violations while the move dialog is open", async () => {
    mockApi(routes());
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Move What is dependency injection?" }));
    await screen.findByRole("dialog", { name: "Move item" });
    await expectNoA11yViolations(document.body);
  });
});
