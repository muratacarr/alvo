import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ApiError, api } from "../api/client";
import { describeError } from "../errors";

interface Project {
  id: string;
  title: string;
  description: string | null;
  archived: boolean;
}

interface Page {
  items: Project[];
  next_cursor: string | null;
}

const PAGE_SIZE = 50;

const buttonClass =
  "rounded-md border border-slate-500 px-3 py-1 text-sm font-medium text-slate-900 hover:bg-slate-100";

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [titleInvalid, setTitleInvalid] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const projects = useInfiniteQuery({
    queryKey: ["projects", { showArchived }],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      api.get<Page>("/api/v1/projects", {
        limit: PAGE_SIZE,
        cursor: pageParam,
        include_archived: showArchived ? true : undefined,
      }),
    getNextPageParam: (last) => last.next_cursor,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["projects"] });

  const create = useMutation({
    mutationFn: (input: { title: string; description?: string }) =>
      api.post("/api/v1/projects", input),
    onSuccess: async () => {
      setTitle("");
      setDescription("");
      setFormError(null);
      setTitleInvalid(false);
      setNotice("Project created.");
      await refresh();
    },
    onError: (error) => {
      setNotice(null);
      setTitleInvalid(error instanceof ApiError && error.fields.includes("body.title"));
      setFormError(describeError(error, "Could not create the project. Please try again."));
    },
  });

  const archive = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/projects/${id}`),
    onSuccess: refresh,
  });
  const restore = useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/projects/${id}/unarchive`),
    onSuccess: refresh,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setNotice(null);
    const cleanTitle = title.trim();
    if (cleanTitle === "") {
      setTitleInvalid(true);
      setFormError("Enter a title.");
      return;
    }
    setTitleInvalid(false);
    setFormError(null);
    const cleanDescription = description.trim();
    create.mutate(
      cleanDescription === ""
        ? { title: cleanTitle }
        : { title: cleanTitle, description: cleanDescription },
    );
  }

  const items = projects.data?.pages.flatMap((page) => page.items) ?? [];
  const rowError = archive.error ?? restore.error;

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-slate-900">Projects</h1>

      <section aria-labelledby="create-heading">
        <h2 id="create-heading" className="mb-3 text-xl font-semibold text-slate-900">
          Create a project
        </h2>
        <form onSubmit={submit} noValidate className="max-w-xl space-y-4">
          <div>
            <label htmlFor="project-title" className="mb-1 block font-medium text-slate-900">
              Title
            </label>
            <input
              id="project-title"
              type="text"
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              aria-invalid={titleInvalid}
              aria-describedby={formError ? "form-error" : undefined}
              className="w-full rounded-md border border-slate-500 px-3 py-2 text-slate-900"
            />
          </div>
          <div>
            <label htmlFor="project-description" className="mb-1 block font-medium text-slate-900">
              Description (optional)
            </label>
            <textarea
              id="project-description"
              maxLength={2000}
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="w-full rounded-md border border-slate-500 px-3 py-2 text-slate-900"
            />
          </div>
          {formError && (
            <p id="form-error" role="alert" className="rounded-md bg-red-50 p-3 text-red-900">
              {formError}
            </p>
          )}
          {notice && (
            <p role="status" className="rounded-md bg-green-50 p-3 text-green-900">
              {notice}
            </p>
          )}
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-indigo-700 px-4 py-2 font-semibold text-white hover:bg-indigo-800 disabled:opacity-70"
          >
            {create.isPending ? "Creating…" : "Create project"}
          </button>
        </form>
      </section>

      <section aria-labelledby="list-heading">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="list-heading" className="text-xl font-semibold text-slate-900">
            Your projects
          </h2>
          <label className="flex items-center gap-2 text-slate-900">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
              className="size-4"
            />
            Show archived
          </label>
        </div>

        {rowError && (
          <p role="alert" className="mb-3 rounded-md bg-red-50 p-3 text-red-900">
            {describeError(rowError, "That change could not be saved. Please try again.")}
          </p>
        )}

        {projects.isPending && (
          <p role="status" className="text-slate-700">
            Loading projects…
          </p>
        )}

        {projects.isError && (
          <div role="alert" className="space-y-2 rounded-md bg-red-50 p-3 text-red-900">
            <p>{describeError(projects.error, "Could not load projects.")}</p>
            <button type="button" className={buttonClass} onClick={() => void projects.refetch()}>
              Try again
            </button>
          </div>
        )}

        {projects.isSuccess && items.length === 0 && (
          <p className="text-slate-700">No projects yet. Create your first one above.</p>
        )}

        {items.length > 0 && (
          <ul className="space-y-3">
            {items.map((project) => (
              <li
                key={project.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-300 p-4"
              >
                <div className="min-w-0">
                  <h3 className="break-words text-lg font-semibold text-slate-900">
                    {project.title}
                  </h3>
                  {project.description && (
                    <p className="break-words text-slate-700">{project.description}</p>
                  )}
                  {project.archived && (
                    <span className="mt-1 inline-block rounded bg-slate-200 px-2 py-0.5 text-sm text-slate-900">
                      Archived
                    </span>
                  )}
                </div>
                {project.archived ? (
                  <button
                    type="button"
                    className={buttonClass}
                    aria-label={`Restore ${project.title}`}
                    onClick={() => restore.mutate(project.id)}
                  >
                    Restore
                  </button>
                ) : (
                  <button
                    type="button"
                    className={buttonClass}
                    aria-label={`Archive ${project.title}`}
                    onClick={() => archive.mutate(project.id)}
                  >
                    Archive
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {projects.hasNextPage && (
          <button
            type="button"
            className={`${buttonClass} mt-4`}
            disabled={projects.isFetchingNextPage}
            onClick={() => void projects.fetchNextPage()}
          >
            {projects.isFetchingNextPage ? "Loading…" : "Load more"}
          </button>
        )}
      </section>
    </div>
  );
}
