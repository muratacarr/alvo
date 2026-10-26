import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../test/a11y";
import { failNetwork, mockApi, type Handler } from "../test/mockApi";
import { ME, project, renderWithProviders } from "../test/render";
import { ImportPage } from "./ImportPage";

const PID = "22222222-2222-4222-8222-222222222222";
const BASE = `/api/v1/projects/${PID}`;

const session = {
  "GET /api/v1/auth/me": { json: ME },
  "GET /api/v1/auth/csrf": { json: { csrf_token: "csrf-1" } },
};

const counts = (over: Record<string, number> = {}) => ({
  new_items: 2,
  new_modules: 1,
  new_topics: 1,
  duplicate_external_id: 0,
  duplicate_content: 1,
  duplicate_in_file: 0,
  ambiguous: 0,
  invalid: 0,
  ...over,
});

const preview = (over: Record<string, unknown> = {}) => ({
  json: {
    program_title: "Backend Developer Interview",
    counts: counts(),
    new_samples: [
      { path: "modules[0].topics[0].items[0]", type: "question", prompt: "What is DI?" },
      { path: "modules[0].topics[0].items[1]", type: "phrase", prompt: "break the ice" },
    ],
    ambiguous: [],
    invalid: [],
    ...over,
  },
});

function routes(extra: Record<string, Handler> = {}): Record<string, Handler> {
  return {
    ...session,
    [`GET ${BASE}`]: { json: project({ id: PID, title: "Backend Interview" }) },
    [`POST ${BASE}/imports/preview`]: preview(),
    ...extra,
  };
}

function renderImport() {
  return renderWithProviders(
    <Routes>
      <Route path="/projects/:projectId/import" element={<ImportPage />} />
      <Route path="/projects/:projectId" element={<p>Project page</p>} />
    </Routes>,
    `/projects/${PID}/import`,
  );
}

const FILE_TEXT = '{"schemaVersion": "1.0",  "program": {"title": "T", "modules": []}}';
const jsonFile = (text = FILE_TEXT, name = "interview.json") =>
  new File([text], name, { type: "application/json" });

async function chooseFile(file = jsonFile()) {
  await userEvent.upload(await screen.findByLabelText("Import file (JSON)"), file);
}

async function preparePreview() {
  await chooseFile();
  await userEvent.click(screen.getByRole("button", { name: "Preview import" }));
  await screen.findByText("Backend Developer Interview");
}

afterEach(() => vi.restoreAllMocks());

describe("ImportPage: choosing and previewing", () => {
  it("asks for a JSON file and offers the template, schema and project export", async () => {
    mockApi(routes());
    const { container } = renderImport();
    expect(await screen.findByRole("heading", { name: "Import and export" })).toBeInTheDocument();
    const input = screen.getByLabelText("Import file (JSON)");
    expect(input).toHaveAttribute("accept", expect.stringContaining(".json"));
    expect(screen.getByRole("button", { name: "Preview import" })).toBeDisabled();
    for (const name of ["Download sample file", "Download schema", "Export this project"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    await expectNoA11yViolations(container);
  });

  it("refuses a file over 2 MiB without sending anything", async () => {
    const { calls } = mockApi(routes());
    renderImport();
    const big = new File([new Uint8Array(2 * 1024 * 1024 + 1)], "big.json", { type: "application/json" });
    await chooseFile(big);
    expect(await screen.findByRole("alert")).toHaveTextContent("larger than 2 MiB");
    expect(screen.getByRole("button", { name: "Preview import" })).toBeDisabled();
    expect(calls.filter((c) => c.method === "POST")).toEqual([]);
  });

  it("sends the file text exactly as it is to the preview, with the CSRF token", async () => {
    const { calls } = mockApi(routes());
    renderImport();
    await preparePreview();
    const request = calls.find((c) => c.path.startsWith(`${BASE}/imports/preview`));
    expect(request?.rawBody).toBe(FILE_TEXT);
    expect(request?.path).toBe(`${BASE}/imports/preview?ambiguous=skip`);
    expect(request?.headers["x-csrf-token"]).toBe("csrf-1");
  });

  it("explains what the import would do", async () => {
    mockApi(routes());
    renderImport();
    await preparePreview();
    const summary = screen.getByRole("region", { name: "Preview" });
    expect(within(summary).getByText("New items")).toBeInTheDocument();
    expect(within(summary).getByTestId("count-new_items")).toHaveTextContent("2");
    expect(within(summary).getByTestId("count-duplicate_content")).toHaveTextContent("1");
    expect(within(summary).getByText("What is DI?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import 2 new items" })).toBeEnabled();
  });

  it("shows file content as text, never as markup (XSS)", async () => {
    const payload = '<img src=x onerror="window.__pwned=1">';
    mockApi(
      routes({
        [`POST ${BASE}/imports/preview`]: preview({
          new_samples: [{ path: "p", type: "question", prompt: payload }],
        }),
      }),
    );
    const { container } = renderImport();
    await preparePreview();
    await screen.findByText(payload);
    expect(container.querySelector("img")).toBeNull();
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  });

  it("lists possible duplicates and re-previews when the choice changes", async () => {
    const { calls } = mockApi(
      routes({
        [`POST ${BASE}/imports/preview`]: (call) =>
          call.path.includes("ambiguous=add")
            ? preview({ counts: counts({ new_items: 3, ambiguous: 1 }) })
            : preview({
                counts: counts({ ambiguous: 1 }),
                ambiguous: [
                  { path: "modules[0].topics[0].items[2]", prompt: "Whats your name", existing_prompt: "What's your name?" },
                ],
              }),
      }),
    );
    renderImport();
    await preparePreview();
    expect(screen.getByText("What's your name?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Add them anyway" }));
    expect(await screen.findByRole("button", { name: "Import 3 new items" })).toBeInTheDocument();
    expect(calls.filter((c) => c.path.includes("imports/preview"))).toHaveLength(2);
    expect(calls.at(-1)?.path).toContain("ambiguous=add");
  });

  it("lists invalid entries and does not allow importing", async () => {
    mockApi(
      routes({
        [`POST ${BASE}/imports/preview`]: preview({
          counts: counts({ invalid: 1 }),
          invalid: [{ path: "modules[0].topics[0].items[3]", reasons: ["id:extra_forbidden"] }],
        }),
      }),
    );
    renderImport();
    await preparePreview();
    expect(screen.getByText("modules[0].topics[0].items[3]")).toBeInTheDocument();
    expect(screen.getByText(/id:extra_forbidden/)).toBeInTheDocument();
    expect(screen.getByText(/Fix the invalid items/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Import / })).toBeDisabled();
  });

  it("says when there is nothing new to import", async () => {
    mockApi(
      routes({
        [`POST ${BASE}/imports/preview`]: preview({
          counts: counts({ new_items: 0, new_modules: 0, new_topics: 0, duplicate_content: 2 }),
          new_samples: [],
        }),
      }),
    );
    renderImport();
    await preparePreview();
    expect(screen.getByText(/Nothing new to import/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Import / })).toBeDisabled();
  });

  it("forgets the preview when another file is chosen", async () => {
    mockApi(routes());
    renderImport();
    await preparePreview();
    await chooseFile(jsonFile('{"other": true}', "other.json"));
    expect(screen.queryByText("Backend Developer Interview")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Import \d/ })).not.toBeInTheDocument();
  });

  it.each([
    [422, "invalid_json", "not valid JSON"],
    [422, "duplicate_key", "repeats a key"],
    [422, "unsupported_schema_version", "unsupported schemaVersion"],
    [422, "too_many_items", "too many items"],
    [413, "payload_too_large", "larger than 2 MiB"],
    [429, "rate_limited", "Too many imports"],
  ])("explains a %s %s response in plain words", async (status, code, expected) => {
    mockApi(routes({ [`POST ${BASE}/imports/preview`]: { status, json: { error: code } } }));
    renderImport();
    await chooseFile();
    await userEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(expected);
  });

  it("says when the server cannot be reached", async () => {
    mockApi(routes());
    renderImport();
    await chooseFile();
    failNetwork();
    await userEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("has no accessibility violations after a preview", async () => {
    mockApi(routes());
    const { container } = renderImport();
    await preparePreview();
    await expectNoA11yViolations(container);
  });
});

describe("ImportPage: importing", () => {
  const committed = {
    json: { job_id: "j1", replayed: false, counts: counts({ new_items: 2 }) },
  };

  it("imports with an idempotency key and the same choices as the preview", async () => {
    const { calls } = mockApi(routes({ [`POST ${BASE}/imports/commit`]: committed }));
    renderImport();
    await preparePreview();
    await userEvent.click(screen.getByRole("button", { name: "Import 2 new items" }));
    expect(await screen.findByText(/Imported 2 new items/)).toBeInTheDocument();
    const commit = calls.find((c) => c.path.startsWith(`${BASE}/imports/commit`));
    expect(commit?.rawBody).toBe(FILE_TEXT);
    expect(commit?.path).toBe(`${BASE}/imports/commit?ambiguous=skip`);
    expect(commit?.headers["idempotency-key"]).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(commit?.headers["x-csrf-token"]).toBe("csrf-1");
    expect(screen.getByRole("link", { name: "Back to the project" })).toHaveAttribute("href", `/projects/${PID}`);
  });

  it("reuses the same idempotency key when the import is retried", async () => {
    let attempts = 0;
    const { calls } = mockApi(
      routes({
        [`POST ${BASE}/imports/commit`]: () => {
          attempts += 1;
          return attempts === 1 ? { status: 429, json: { error: "rate_limited" } } : committed.json && committed;
        },
      }),
    );
    renderImport();
    await preparePreview();
    await userEvent.click(screen.getByRole("button", { name: "Import 2 new items" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many imports");
    await userEvent.click(screen.getByRole("button", { name: "Import 2 new items" }));
    expect(await screen.findByText(/Imported 2 new items/)).toBeInTheDocument();
    const keys = calls.filter((c) => c.path.includes("imports/commit")).map((c) => c.headers["idempotency-key"]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
  });

  it("uses a fresh key for a different file", async () => {
    const { calls } = mockApi(routes({ [`POST ${BASE}/imports/commit`]: committed }));
    renderImport();
    await preparePreview();
    await userEvent.click(screen.getByRole("button", { name: "Import 2 new items" }));
    await screen.findByText(/Imported 2 new items/);
    await chooseFile(jsonFile('{"schemaVersion":"1.0","program":{"title":"U","modules":[]}}', "second.json"));
    await userEvent.click(screen.getByRole("button", { name: "Preview import" }));
    await userEvent.click(await screen.findByRole("button", { name: "Import 2 new items" }));
    await waitFor(() => expect(calls.filter((c) => c.path.includes("imports/commit"))).toHaveLength(2));
    const keys = calls.filter((c) => c.path.includes("imports/commit")).map((c) => c.headers["idempotency-key"]);
    expect(keys[0]).not.toBe(keys[1]);
  });

  it("mentions when a result was replayed from an earlier identical import", async () => {
    mockApi(
      routes({
        [`POST ${BASE}/imports/commit`]: { json: { job_id: "j1", replayed: true, counts: counts() } },
      }),
    );
    renderImport();
    await preparePreview();
    await userEvent.click(screen.getByRole("button", { name: "Import 2 new items" }));
    expect(await screen.findByText(/already imported earlier/)).toBeInTheDocument();
  });

  it("does not allow importing into an archived project and says why", async () => {
    mockApi(routes({ [`GET ${BASE}`]: { json: project({ id: PID, title: "Old", archived: true }) } }));
    renderImport();
    await preparePreview();
    expect(screen.getByText(/This project is archived/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Import / })).toBeDisabled();
  });

  it("explains an unknown project", async () => {
    mockApi({ ...session, [`GET ${BASE}`]: { status: 404, json: { error: "not_found" } } });
    renderImport();
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();
  });
});

describe("ImportPage: downloads", () => {
  function captureDownloads() {
    const downloads: { name: string; href: string }[] = [];
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test-file");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push({ name: this.download, href: this.href });
    });
    return downloads;
  }

  it("downloads the project export under a fixed file name", async () => {
    const downloads = captureDownloads();
    const { calls } = mockApi(routes({ [`GET ${BASE}/export`]: { json: { schemaVersion: "1.0" } } }));
    renderImport();
    await userEvent.click(await screen.findByRole("button", { name: "Export this project" }));
    await waitFor(() => expect(downloads).toHaveLength(1));
    expect(downloads[0]?.name).toBe("alvo-export.json");
    expect(calls.some((c) => c.path === `${BASE}/export`)).toBe(true);
  });

  it("downloads the sample file and the schema", async () => {
    const downloads = captureDownloads();
    mockApi(
      routes({
        "GET /api/v1/templates/import/v1/sample": { json: { schemaVersion: "1.0" } },
        "GET /api/v1/templates/import/v1/schema": { json: { type: "object" } },
      }),
    );
    renderImport();
    await userEvent.click(await screen.findByRole("button", { name: "Download sample file" }));
    await userEvent.click(screen.getByRole("button", { name: "Download schema" }));
    await waitFor(() => expect(downloads).toHaveLength(2));
    expect(downloads.map((d) => d.name)).toEqual(["alvo-import-sample.json", "alvo-import-schema.json"]);
  });

  it("reports a failed download", async () => {
    captureDownloads();
    mockApi(routes({ [`GET ${BASE}/export`]: { status: 404, json: { error: "not_found" } } }));
    renderImport();
    await userEvent.click(await screen.findByRole("button", { name: "Export this project" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not download");
  });
});
