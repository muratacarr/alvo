import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, Form, Input, List, Tag, Typography } from "antd";
import { useState } from "react";

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

  function submit() {
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
      <Typography.Title level={1}>Projects</Typography.Title>

      <section aria-labelledby="create-heading">
        <Typography.Title level={2} id="create-heading">
          Create a project
        </Typography.Title>
        <Form
          layout="vertical"
          onFinish={submit}
          requiredMark={false}
          noValidate
          className="max-w-xl"
        >
          <Form.Item label="Title" htmlFor="project-title">
            <Input
              id="project-title"
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              status={titleInvalid ? "error" : undefined}
              aria-invalid={titleInvalid}
              aria-describedby={formError ? "form-error" : undefined}
            />
          </Form.Item>
          <Form.Item label="Description (optional)" htmlFor="project-description">
            <Input.TextArea
              id="project-description"
              maxLength={2000}
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Form.Item>
          {formError && <Alert id="form-error" type="error" title={formError} className="mb-4" />}
          {notice && (
            <p role="status" className="mb-4 rounded-md bg-green-50 p-3 text-green-900">
              {notice}
            </p>
          )}
          <Button type="primary" htmlType="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create project"}
          </Button>
        </Form>
      </section>

      <section aria-labelledby="list-heading">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <Typography.Title level={2} id="list-heading" className="!mb-0">
            Your projects
          </Typography.Title>
          <Checkbox checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)}>
            Show archived
          </Checkbox>
        </div>

        {rowError && (
          <Alert
            type="error"
            title={describeError(rowError, "That change could not be saved. Please try again.")}
            className="mb-3"
          />
        )}

        {projects.isPending && (
          <p role="status" className="text-slate-700">
            Loading projects…
          </p>
        )}

        {projects.isError && (
          <Alert
            type="error"
            title={describeError(projects.error, "Could not load projects.")}
            action={<Button onClick={() => void projects.refetch()}>Try again</Button>}
          />
        )}

        {projects.isSuccess && items.length === 0 && (
          <Typography.Paragraph>No projects yet. Create your first one above.</Typography.Paragraph>
        )}

        {items.length > 0 && (
          <List
            bordered
            dataSource={items}
            renderItem={(project) => (
              <List.Item key={project.id}>
                <div className="flex w-full flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <Typography.Title level={3} className="!mb-1 break-words !text-lg">
                    {project.title}
                  </Typography.Title>
                  {project.description && (
                    <Typography.Paragraph className="!mb-1 break-words">
                      {project.description}
                    </Typography.Paragraph>
                  )}
                  {project.archived && <Tag>Archived</Tag>}
                </div>
                {project.archived ? (
                  <Button
                    aria-label={`Restore ${project.title}`}
                    onClick={() => restore.mutate(project.id)}
                  >
                    Restore
                  </Button>
                ) : (
                  <Button
                    aria-label={`Archive ${project.title}`}
                    onClick={() => archive.mutate(project.id)}
                  >
                    Archive
                  </Button>
                )}
                </div>
              </List.Item>
            )}
          />
        )}

        {projects.hasNextPage && (
          <Button
            className="mt-4"
            disabled={projects.isFetchingNextPage}
            onClick={() => void projects.fetchNextPage()}
          >
            {projects.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        )}
      </section>
    </div>
  );
}
