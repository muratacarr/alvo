import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Radio, Tag, Typography } from "antd";
import { useRef, useState, type ChangeEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, api } from "../api/client";
import type { ProjectDto } from "../api/types";
import { describeError, describeImportError } from "../errors";

const MAX_BYTES = 2 * 1024 * 1024;

type Ambiguous = "skip" | "add";

interface Counts {
  new_items: number;
  new_modules: number;
  new_topics: number;
  duplicate_external_id: number;
  duplicate_content: number;
  duplicate_in_file: number;
  ambiguous: number;
  invalid: number;
}

interface PreviewDto {
  program_title: string;
  counts: Counts;
  new_samples: { path: string; type: string; prompt: string }[];
  ambiguous: { path: string; prompt: string; existing_prompt: string }[];
  invalid: { path: string; reasons: string[] }[];
}

interface CommitDto {
  job_id: string;
  replayed: boolean;
  counts: Counts;
}

const COUNT_LABELS: [keyof Counts, string][] = [
  ["new_items", "New items"],
  ["new_modules", "New modules"],
  ["new_topics", "New topics"],
  ["duplicate_external_id", "Already imported (same id)"],
  ["duplicate_content", "Already in the project (same content)"],
  ["duplicate_in_file", "Repeated in the file"],
  ["ambiguous", "Possible duplicates"],
  ["invalid", "Invalid"],
];

const SIZE_MESSAGE = "This file is larger than 2 MiB, which is the import limit.";

function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ImportPage() {
  const { projectId = "" } = useParams();
  const base = `/api/v1/projects/${projectId}`;
  const queryClient = useQueryClient();

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.get<ProjectDto>(base),
  });

  const [fileText, setFileText] = useState<string | null>(null);
  const [choice, setChoice] = useState<Ambiguous>("skip");
  const [preview, setPreview] = useState<PreviewDto | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // One key per file and choice: a retry of the same import is recognised by the server, while a
  // different file or a different choice is a different import.
  const keyRef = useRef<{ choice: Ambiguous; key: string } | null>(null);

  const previewMutation = useMutation({
    mutationFn: ({ text, ambiguous }: { text: string; ambiguous: Ambiguous }) =>
      api.postText<PreviewDto>(`${base}/imports/preview`, text, { query: { ambiguous } }),
    onSuccess: (data) => setPreview(data),
    onError: (error) => setNotice(describeImportError(error, "Could not preview the file.")),
  });

  const commitMutation = useMutation({
    mutationFn: ({ text, ambiguous, key }: { text: string; ambiguous: Ambiguous; key: string }) =>
      api.postText<CommitDto>(`${base}/imports/commit`, text, {
        query: { ambiguous },
        headers: { "Idempotency-Key": key },
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["modules", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["topics", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["items", projectId] }),
      ]);
    },
    onError: (error) => setNotice(describeImportError(error, "Could not import the file.")),
  });

  const downloadMutation = useMutation({
    mutationFn: async ({ path, name }: { path: string; name: string }) => {
      saveBlob(await api.getBlob(path), name);
    },
    onError: (error) => setNotice(describeError(error, "Could not download the file. Try again.")),
  });

  function reset() {
    setPreview(null);
    setNotice(null);
    setChoice("skip");
    keyRef.current = null;
    commitMutation.reset();
  }

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    reset();
    setFileText(null);
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setNotice(SIZE_MESSAGE);
      return;
    }
    setFileText(await file.text());
  }

  function runPreview(ambiguous: Ambiguous) {
    if (fileText === null) return;
    setNotice(null);
    previewMutation.mutate({ text: fileText, ambiguous });
  }

  function runCommit() {
    if (fileText === null) return;
    if (keyRef.current === null || keyRef.current.choice !== choice) {
      keyRef.current = { choice, key: crypto.randomUUID() };
    }
    setNotice(null);
    commitMutation.mutate({ text: fileText, ambiguous: choice, key: keyRef.current.key });
  }

  function download(path: string, name: string) {
    setNotice(null);
    downloadMutation.mutate({ path, name });
  }

  if (project.isPending) {
    return (
      <p role="status" className="text-slate-700">
        Loading project…
      </p>
    );
  }

  if (project.isError) {
    if (project.error instanceof ApiError && project.error.status === 404) {
      return (
        <div>
          <Typography.Title level={1}>Project not found</Typography.Title>
          <Typography.Paragraph>It may have been removed, or it is not yours.</Typography.Paragraph>
          <Link to="/" className="font-medium text-indigo-800 underline">
            Back to projects
          </Link>
        </div>
      );
    }
    return (
      <Alert
        type="error"
        title={describeError(project.error, "Could not load the project.")}
        action={<Button onClick={() => void project.refetch()}>Try again</Button>}
      />
    );
  }

  const archived = project.data.archived;
  const imported = commitMutation.data;
  const counts = preview?.counts;
  const newTotal = counts ? counts.new_items + counts.new_modules + counts.new_topics : 0;
  const blocked = counts ? counts.invalid > 0 : false;
  const canImport = preview !== null && !blocked && newTotal > 0 && !archived && imported === undefined;

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${projectId}`} className="text-sm font-medium text-indigo-800 underline">
          {project.data.title}
        </Link>
        <Typography.Title level={1} className="!mt-2 !mb-0">
          Import and export
        </Typography.Title>
      </div>

      {archived && (
        <p className="text-slate-800">This project is archived, so nothing can be imported into it.</p>
      )}

      {notice !== null && <Alert type="error" title={notice} />}

      <section aria-labelledby="export-heading" className="space-y-3">
        <Typography.Title level={2} id="export-heading">
          Download
        </Typography.Title>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => download(`${base}/export`, "alvo-export.json")}>Export this project</Button>
          <Button onClick={() => download("/api/v1/templates/import/v1/sample", "alvo-import-sample.json")}>
            Download sample file
          </Button>
          <Button onClick={() => download("/api/v1/templates/import/v1/schema", "alvo-import-schema.json")}>
            Download schema
          </Button>
        </div>
      </section>

      <section aria-labelledby="import-heading" className="space-y-3">
        <Typography.Title level={2} id="import-heading">
          Import
        </Typography.Title>
        <div className="flex flex-col gap-2">
          <label htmlFor="import-file" className="font-medium">
            Import file (JSON)
          </label>
          <input
            id="import-file"
            type="file"
            accept=".json,application/json"
            onChange={(event) => void onFile(event)}
            className="max-w-full"
          />
        </div>
        <Button
          type="primary"
          disabled={fileText === null}
          loading={previewMutation.isPending}
          onClick={() => runPreview(choice)}
        >
          Preview import
        </Button>
      </section>

      {preview !== null && counts !== undefined && (
        <section aria-labelledby="preview-heading" className="space-y-4">
          <Typography.Title level={2} id="preview-heading">
            Preview
          </Typography.Title>
          <p className="break-words">
            Program: <strong>{preview.program_title}</strong>
          </p>
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-1">
            {COUNT_LABELS.map(([key, label]) => (
              <div key={key} className="contents">
                <dt>{label}</dt>
                <dd data-testid={`count-${key}`} className="text-right font-medium">
                  {counts[key]}
                </dd>
              </div>
            ))}
          </dl>

          {preview.new_samples.length > 0 && (
            <div>
              <Typography.Title level={3}>Examples of new items</Typography.Title>
              <ul className="space-y-1">
                {preview.new_samples.map((sample) => (
                  <li key={sample.path} className="break-words">
                    <Tag>{sample.type}</Tag> <span>{sample.prompt}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {counts.ambiguous > 0 && (
            <div className="space-y-2">
              <Typography.Title level={3}>Possible duplicates</Typography.Title>
              {preview.ambiguous.length > 0 && (
                <ul className="space-y-1">
                  {preview.ambiguous.map((entry) => (
                    <li key={entry.path} className="break-words">
                      <span>{entry.prompt}</span> looks like <span>{entry.existing_prompt}</span>
                    </li>
                  ))}
                </ul>
              )}
              <Radio.Group
                value={choice}
                onChange={(event) => {
                  const next = event.target.value as Ambiguous;
                  setChoice(next);
                  runPreview(next);
                }}
                aria-label="What to do with possible duplicates"
                options={[
                  { value: "skip", label: "Skip (recommended)" },
                  { value: "add", label: "Add them anyway" },
                ]}
              />
            </div>
          )}

          {preview.invalid.length > 0 && (
            <div className="space-y-2">
              <Typography.Title level={3}>Invalid entries</Typography.Title>
              <ul className="space-y-1">
                {preview.invalid.map((entry) => (
                  <li key={entry.path} className="break-words">
                    <code>{entry.path}</code> <span>{entry.reasons.join(", ")}</span>
                  </li>
                ))}
              </ul>
              <p>Fix the invalid items in the file and choose it again.</p>
            </div>
          )}

          {!blocked && newTotal === 0 && <p>Nothing new to import: everything is already in the project.</p>}

          <Button type="primary" disabled={!canImport} loading={commitMutation.isPending} onClick={runCommit}>
            {`Import ${counts.new_items} new ${counts.new_items === 1 ? "item" : "items"}`}
          </Button>
        </section>
      )}

      {imported !== undefined && (
        <section aria-labelledby="done-heading" className="space-y-2">
          <Typography.Title level={2} id="done-heading">
            Done
          </Typography.Title>
          <p role="status">
            {`Imported ${imported.counts.new_items} new ${imported.counts.new_items === 1 ? "item" : "items"}.`}
            {imported.replayed && " This file was already imported earlier, so nothing was added twice."}
          </p>
          <Link to={`/projects/${projectId}`} className="font-medium text-indigo-800 underline">
            Back to the project
          </Link>
        </section>
      )}
    </div>
  );
}
