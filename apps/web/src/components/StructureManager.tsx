import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Input, Modal, Typography } from "antd";
import { useState } from "react";

import { api } from "../api/client";
import type { ModuleDto, TopicDto } from "../api/types";
import { describeError } from "../errors";

type Kind = "module" | "topic";

interface Target {
  kind: Kind;
  id: string;
  title: string;
}

interface Props {
  projectId: string;
  modules: ModuleDto[];
  topics: TopicDto[];
  /** Called after a topic was archived, so the screen can leave it if it was open. */
  onTopicArchived: (topicId: string) => void;
}

const path = (projectId: string, target: Target) =>
  `/api/v1/projects/${projectId}/${target.kind === "module" ? "modules" : "topics"}/${target.id}`;

function RenameDialog({
  target,
  error,
  saving,
  onCancel,
  onSubmit,
}: {
  target: Target;
  error: string | null;
  saving: boolean;
  onCancel: () => void;
  onSubmit: (title: string | null) => void;
}) {
  const [name, setName] = useState(target.title);
  const [problem, setProblem] = useState<string | null>(null);

  function submit() {
    const title = name.trim();
    if (title === "") {
      setProblem("Enter a name.");
      return;
    }
    setProblem(null);
    onSubmit(title === target.title ? null : title);
  }

  return (
    <Modal open title={`Rename ${target.kind}`} footer={null} onCancel={onCancel} destroyOnHidden>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className="space-y-3"
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="rename-input" className="font-medium">
            New name
          </label>
          <Input
            id="rename-input"
            maxLength={200}
            value={name}
            onChange={(event) => setName(event.target.value)}
            status={problem ? "error" : undefined}
            aria-invalid={problem !== null}
            aria-describedby={problem ? "rename-problem" : undefined}
          />
          {problem && (
            <p id="rename-problem" className="text-red-800">
              {problem}
            </p>
          )}
        </div>
        {error && <Alert type="error" title={error} />}
        <div className="flex gap-2">
          <Button type="primary" htmlType="submit" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}

function ArchiveDialog({
  target,
  error,
  saving,
  onCancel,
  onConfirm,
}: {
  target: Target;
  error: string | null;
  saving: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const consequence =
    target.kind === "module"
      ? "Its topics and items will no longer be shown."
      : "Its items will no longer be shown.";
  return (
    <Modal open title={`Archive ${target.kind}`} footer={null} onCancel={onCancel} destroyOnHidden>
      <div className="space-y-3">
        <p className="break-words">{`Archive the ${target.kind} "${target.title}"?`}</p>
        <p>{`${consequence} You cannot undo this in the app yet.`}</p>
        {error && <Alert type="error" title={error} />}
        <div className="flex gap-2">
          <Button type="primary" danger disabled={saving} onClick={onConfirm}>
            {saving ? "Archiving…" : "Archive"}
          </Button>
          <Button onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </Modal>
  );
}

export function StructureManager({ projectId, modules, topics, onTopicArchived }: Props) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rename, setRename] = useState<Target | null>(null);
  const [archive, setArchive] = useState<Target | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["modules", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["topics", projectId] }),
    ]);

  const renameMutation = useMutation({
    mutationFn: ({ target, title }: { target: Target; title: string }) =>
      api.patch(path(projectId, target), { title }),
    onSuccess: async () => {
      setRename(null);
      await refresh();
    },
    onError: (e) => setError(describeError(e, "Could not rename. Please try again.")),
  });

  const archiveMutation = useMutation({
    mutationFn: (target: Target) => api.delete(path(projectId, target)),
    onSuccess: async (_data, target) => {
      setArchive(null);
      if (target.kind === "topic") onTopicArchived(target.id);
      await refresh();
    },
    onError: (e) => setError(describeError(e, "Could not archive. Please try again.")),
  });

  function startRename(target: Target) {
    setError(null);
    setRename(target);
  }

  function startArchive(target: Target) {
    setError(null);
    setArchive(target);
  }

  const row = (kind: Kind, id: string, title: string) => (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="min-w-0 break-words">{title}</span>
      <span className="flex gap-2">
        <Button size="small" aria-label={`Rename ${kind} ${title}`} onClick={() => startRename({ kind, id, title })}>
          Rename
        </Button>
        <Button size="small" aria-label={`Archive ${kind} ${title}`} onClick={() => startArchive({ kind, id, title })}>
          Archive
        </Button>
      </span>
    </div>
  );

  return (
    <div>
      <Button aria-expanded={open} aria-controls="manage-structure" onClick={() => setOpen((value) => !value)}>
        Manage modules and topics
      </Button>
      {open && (
        <section id="manage-structure" aria-labelledby="manage-heading" className="mt-3 space-y-3">
          <Typography.Title level={2} id="manage-heading" className="!text-xl">
            Rename or archive
          </Typography.Title>
          {modules.length === 0 && <p>No modules yet.</p>}
          <ul className="space-y-3">
            {modules.map((module) => (
              <li key={module.id} className="space-y-2">
                {row("module", module.id, module.title)}
                <ul className="ml-4 space-y-2 border-l pl-3">
                  {topics
                    .filter((topic) => topic.module_id === module.id)
                    .map((topic) => (
                      <li key={topic.id}>{row("topic", topic.id, topic.title)}</li>
                    ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      {rename && (
        <RenameDialog
          key={rename.id}
          target={rename}
          error={error}
          saving={renameMutation.isPending}
          onCancel={() => setRename(null)}
          onSubmit={(title) => {
            if (title === null) {
              setRename(null); // nothing changed: no request
              return;
            }
            renameMutation.mutate({ target: rename, title });
          }}
        />
      )}
      {archive && (
        <ArchiveDialog
          target={archive}
          error={error}
          saving={archiveMutation.isPending}
          onCancel={() => setArchive(null)}
          onConfirm={() => archiveMutation.mutate(archive)}
        />
      )}
    </div>
  );
}
