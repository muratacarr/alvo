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
const item = (over: Record<string, unknown> = {}) => ({
  id: I1,
  project_id: PID,
  topic_id: T1,
  type: "question",
  prompt: "What is dependency injection?",
  sample_answer: "Old answer",
  translation: null,
  keywords: ["coupling", "testing"],
  tags: [],
  follow_up_questions: [],
  difficulty: 2,
  external_id: null,
  practice_modes: [],
  archived: false,
  ...stamp,
  ...over,
});
const page = (items: unknown[], next_cursor: string | null = null) => ({
  json: { items, next_cursor },
});

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
    [`GET ${BASE}/items`]: page([item()]),
    ...extra,
  };
}

function renderDetail(path = `/projects/${PID}`) {
  return renderWithProviders(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
      <Route path="/" element={<p>Projects home</p>} />
    </Routes>,
    path,
  );
}

async function selectTopic(name: string) {
  // The clickable part of a tree row is its title text, as for a real user.
  await userEvent.click(await screen.findByText(name));
}

describe("ProjectDetailPage: structure", () => {
  it("shows the project and its modules and topics", async () => {
    mockApi(routes());
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Backend Interview" })).toBeInTheDocument();
    expect(await screen.findByText("Technical")).toBeInTheDocument();
    expect(screen.getByText("Dependency Injection")).toBeInTheDocument();
    expect(screen.getByText("Teamwork")).toBeInTheDocument();
    expect(screen.getByText(/Select a topic/)).toBeInTheDocument();
  });

  it("loads the items of a chosen topic and asks the server only for that topic", async () => {
    const { calls } = mockApi(routes());
    renderDetail();
    await selectTopic("Dependency Injection");
    expect(await screen.findByText("What is dependency injection?")).toBeInTheDocument();
    const request = calls.find((c) => c.path.startsWith(`${BASE}/items`));
    expect(request?.path).toContain(`topic_id=${T1}`);
  });

  it("opens straight on the topic named in the address (deep link)", async () => {
    mockApi(routes());
    renderDetail(`/projects/${PID}?topic=${T1}`);
    expect(await screen.findByText("What is dependency injection?")).toBeInTheDocument();
  });

  it("renders every piece of content as text, never as markup (XSS)", async () => {
    const payload = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>';
    mockApi(
      routes({
        [`GET ${BASE}/modules`]: page([module_(M1, payload)]),
        [`GET ${BASE}/topics`]: page([topic(T1, M1, payload)]),
        [`GET ${BASE}/items`]: page([item({ prompt: payload, sample_answer: payload, keywords: [payload] })]),
      }),
    );
    const { container } = renderDetail(`/projects/${PID}?topic=${T1}`);
    await screen.findAllByText(payload);
    expect(container.querySelector("img, script")).toBeNull();
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  });

  it("fetches every page of modules when there are more than one", async () => {
    const { calls } = mockApi(
      routes({
        [`GET ${BASE}/modules`]: (call) =>
          call.path.includes("cursor=next")
            ? page([module_(M2, "Second page module")])
            : page([module_(M1, "First page module")], "next"),
        [`GET ${BASE}/topics`]: page([]),
      }),
    );
    renderDetail();
    expect(await screen.findByText("First page module")).toBeInTheDocument();
    expect(await screen.findByText("Second page module")).toBeInTheDocument();
    expect(calls.filter((c) => c.path.startsWith(`${BASE}/modules`))).toHaveLength(2);
  });

  it("adds a module with the CSRF token and shows it", async () => {
    let created = false;
    const { calls } = mockApi(
      routes({
        [`GET ${BASE}/modules`]: () => page(created ? [module_(M1, "Brand new")] : []),
        [`POST ${BASE}/modules`]: () => {
          created = true;
          return { status: 201, json: module_(M1, "Brand new") };
        },
        [`GET ${BASE}/topics`]: page([]),
      }),
    );
    renderDetail();
    await userEvent.type(await screen.findByLabelText("New module title"), "Brand new{Enter}");
    expect(await screen.findByText("Brand new")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ title: "Brand new" });
    expect(post?.headers["x-csrf-token"]).toBe("csrf-1");
    expect(screen.getByLabelText("New module title")).toHaveValue("");
  });

  it("does not send an empty module title", async () => {
    const { calls } = mockApi(routes());
    renderDetail();
    await userEvent.type(await screen.findByLabelText("New module title"), "   {Enter}");
    expect(await screen.findByText("Enter a module title.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("adds a topic to the chosen module", async () => {
    const { calls } = mockApi(
      routes({ [`POST ${BASE}/topics`]: { status: 201, json: topic(T1, M1, "New topic") } }),
    );
    renderDetail();
    await userEvent.click(await screen.findByRole("combobox", { name: "Module for the new topic" }));
    await userEvent.click(await screen.findByRole("option", { name: "Behavioural" }));
    await userEvent.type(screen.getByLabelText("New topic title"), "Conflict{Enter}");
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ module_id: M2, title: "Conflict" });
  });

  it("requires a module and a title before adding a topic", async () => {
    const { calls } = mockApi(routes());
    renderDetail();
    await userEvent.type(await screen.findByLabelText("New topic title"), "Orphan{Enter}");
    expect(await screen.findByText("Choose a module first.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("explains an unknown project instead of showing an empty page", async () => {
    mockApi({ ...session, [`GET ${BASE}`]: { status: 404, json: { error: "not_found" } } });
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to projects" })).toHaveAttribute("href", "/");
  });

  it("offers a retry when the project cannot be loaded", async () => {
    mockApi({ ...session, [`GET ${BASE}`]: { status: 500, json: { error: "internal_error" } } });
    renderDetail();
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the project");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("makes an archived project read-only and says why", async () => {
    mockApi(routes({ [`GET ${BASE}`]: { json: project({ id: PID, title: "Old", archived: true }) } }));
    renderDetail(`/projects/${PID}?topic=${T1}`);
    expect(await screen.findByText(/This project is archived/)).toBeInTheDocument();
    expect(screen.getByLabelText("New module title")).toBeDisabled();
    await screen.findByText("What is dependency injection?");
    expect(screen.queryByRole("button", { name: "Add item" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Archive / })).not.toBeInTheDocument();
  });
});

describe("ProjectDetailPage: items", () => {
  const withTopic = `/projects/${PID}?topic=${T1}`;

  it("shows the details of each item", async () => {
    mockApi(routes());
    renderDetail(withTopic);
    const entry = (await screen.findByText("What is dependency injection?")).closest("li") as HTMLElement;
    expect(within(entry).getByText("Old answer")).toBeInTheDocument();
    expect(within(entry).getByText("coupling")).toBeInTheDocument();
    expect(within(entry).getByText("question")).toBeInTheDocument();
    expect(within(entry).getByText("Difficulty 2")).toBeInTheDocument();
  });

  it("shows an empty state for a topic without items", async () => {
    mockApi(routes({ [`GET ${BASE}/items`]: page([]) }));
    renderDetail(withTopic);
    expect(await screen.findByText(/No items in this topic yet/)).toBeInTheDocument();
  });

  it("adds an item to the selected topic and omits fields left empty", async () => {
    const { calls } = mockApi(
      routes({ [`POST ${BASE}/items`]: { status: 201, json: item({ prompt: "Brand new?" }) } }),
    );
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    const dialog = await screen.findByRole("dialog", { name: "Add item" });
    await userEvent.click(within(dialog).getByRole("radio", { name: "Phrase" }));
    await userEvent.type(within(dialog).getByLabelText("Prompt"), "Brand new?");
    await userEvent.type(within(dialog).getByLabelText("Keywords (comma separated, optional)"), "a, b ,, a");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ topic_id: T1, type: "phrase", prompt: "Brand new?", keywords: ["a", "b"] });
    expect(post?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("validates the prompt before sending", async () => {
    const { calls } = mockApi(routes());
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    const dialog = await screen.findByRole("dialog", { name: "Add item" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    expect(await within(dialog).findByText("Enter a prompt.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("limits field lengths in the item form", async () => {
    mockApi(routes());
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    const dialog = await screen.findByRole("dialog", { name: "Add item" });
    expect(within(dialog).getByLabelText("Prompt")).toHaveAttribute("maxlength", "2000");
    expect(within(dialog).getByLabelText("Sample answer (optional)")).toHaveAttribute("maxlength", "10000");
    expect(within(dialog).getByLabelText("Translation (optional)")).toHaveAttribute("maxlength", "2000");
  });

  it("keeps the dialog open and explains a duplicate", async () => {
    mockApi(routes({ [`POST ${BASE}/items`]: { status: 409, json: { error: "duplicate" } } }));
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    const dialog = await screen.findByRole("dialog", { name: "Add item" });
    await userEvent.type(within(dialog).getByLabelText("Prompt"), "What is dependency injection?");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("already exists in this project");
    expect(screen.getByRole("dialog", { name: "Add item" })).toBeInTheDocument();
  });

  it("explains an archived topic and a network failure", async () => {
    mockApi(routes({ [`POST ${BASE}/items`]: { status: 409, json: { error: "archived" } } }));
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    const dialog = await screen.findByRole("dialog", { name: "Add item" });
    await userEvent.type(within(dialog).getByLabelText("Prompt"), "Anything");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("archived");
    failNetwork();
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent("Cannot reach the server"));
  });

  it("closes the dialog with Escape or Cancel without sending anything", async () => {
    const { calls } = mockApi(routes());
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    await screen.findByRole("dialog", { name: "Add item" });
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Add item" }));
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("edits an item and sends only what changed", async () => {
    const { calls } = mockApi(
      routes({ [`PATCH ${BASE}/items/${I1}`]: { json: item({ prompt: "Changed prompt" }) } }),
    );
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Edit What is dependency injection?" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit item" });
    expect(within(dialog).getByLabelText("Prompt")).toHaveValue("What is dependency injection?");
    expect(within(dialog).getByLabelText("Keywords (comma separated, optional)")).toHaveValue("coupling, testing");
    const prompt = within(dialog).getByLabelText("Prompt");
    await userEvent.clear(prompt);
    await userEvent.type(prompt, "Changed prompt");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toEqual({ prompt: "Changed prompt" });
    expect(patch?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("does not call the server when nothing was changed", async () => {
    const { calls } = mockApi(routes());
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Edit What is dependency injection?" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit item" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.filter((c) => c.method === "PATCH")).toEqual([]);
  });

  it("clears an optional field by sending null", async () => {
    const { calls } = mockApi(routes({ [`PATCH ${BASE}/items/${I1}`]: { json: item() } }));
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Edit What is dependency injection?" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit item" });
    await userEvent.clear(within(dialog).getByLabelText("Sample answer (optional)"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Save item" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ sample_answer: null });
  });

  it("archives an item", async () => {
    let archived = false;
    const { calls } = mockApi(
      routes({
        [`GET ${BASE}/items`]: () => page(archived ? [] : [item()]),
        [`DELETE ${BASE}/items/${I1}`]: () => {
          archived = true;
          return { status: 204 };
        },
      }),
    );
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("button", { name: "Archive What is dependency injection?" }));
    expect(await screen.findByText(/No items in this topic yet/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "DELETE")?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("can show archived items, which have no edit or archive actions", async () => {
    const { calls } = mockApi(
      routes({
        [`GET ${BASE}/items`]: (call) =>
          call.path.includes("include_archived=true") ? page([item({ archived: true })]) : page([]),
      }),
    );
    renderDetail(withTopic);
    await userEvent.click(await screen.findByRole("checkbox", { name: "Show archived items" }));
    const entry = (await screen.findByText("What is dependency injection?")).closest("li") as HTMLElement;
    expect(within(entry).getByText("Archived")).toBeInTheDocument();
    expect(within(entry).queryByRole("button")).not.toBeInTheDocument();
    expect(calls.some((c) => c.path.includes("include_archived=true"))).toBe(true);
  });

  it("loads more items with the server cursor", async () => {
    mockApi(
      routes({
        [`GET ${BASE}/items`]: (call) =>
          call.path.includes("cursor=next-1")
            ? page([item({ id: "d", prompt: "Second page item" })])
            : page([item({ prompt: "First page item" })], "next-1"),
      }),
    );
    renderDetail(withTopic);
    await screen.findByText("First page item");
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("Second page item")).toBeInTheDocument();
  });

  it("shows an error with a retry when items cannot be loaded", async () => {
    mockApi(routes({ [`GET ${BASE}/items`]: { status: 500, json: { error: "internal_error" } } }));
    renderDetail(withTopic);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load items");
  });
});

describe("ProjectDetailPage: accessibility", () => {
  it("has no accessibility violations with a topic open", async () => {
    mockApi(routes());
    const { container } = renderDetail(`/projects/${PID}?topic=${T1}`);
    await screen.findByText("What is dependency injection?");
    await expectNoA11yViolations(container);
  });

  it("has no accessibility violations while the item dialog is open", async () => {
    mockApi(routes());
    renderDetail(`/projects/${PID}?topic=${T1}`);
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    await screen.findByRole("dialog", { name: "Add item" });
    await expectNoA11yViolations(document.body);
  });

  it("lets a keyboard user reach the tree, choose a topic and see its items", async () => {
    const { calls } = mockApi(routes());
    renderDetail();
    await screen.findByText("Technical");
    const tree = screen.getByRole("tree");
    for (let presses = 0; presses < 12 && !tree.contains(document.activeElement); presses += 1) {
      await userEvent.tab();
    }
    expect(tree.contains(document.activeElement)).toBe(true);
    // Focus starts on the first module; one step down is its first topic. Enter chooses it.
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(await screen.findByText("What is dependency injection?")).toBeInTheDocument();
    expect(calls.some((c) => c.path.includes(`topic_id=${T1}`))).toBe(true);
  });
});
