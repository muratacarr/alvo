import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Tag, Typography } from "antd";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError, api } from "../api/client";
import { fetchAll } from "../api/fetchAll";
import type { ModuleDto, ProjectDto, TopicDto } from "../api/types";
import { ItemsPanel } from "../components/ItemsPanel";
import { ProjectStructure } from "../components/ProjectStructure";
import { StructureManager } from "../components/StructureManager";
import { describeError } from "../errors";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const topicId = params.get("topic");

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.get<ProjectDto>(`/api/v1/projects/${projectId}`),
  });
  const base = `/api/v1/projects/${projectId}`;
  const modules = useQuery({
    queryKey: ["modules", projectId],
    queryFn: () => fetchAll<ModuleDto>(`${base}/modules`),
    enabled: project.isSuccess,
  });
  const topics = useQuery({
    queryKey: ["topics", projectId],
    queryFn: () => fetchAll<TopicDto>(`${base}/topics`),
    enabled: project.isSuccess,
  });

  if (project.isPending) {
    return (
      <p role="status" className="text-slate-700">
        Loading project…
      </p>
    );
  }

  if (project.isError) {
    const missing = project.error instanceof ApiError && project.error.status === 404;
    if (missing) {
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

  const readOnly = project.data.archived;
  const topicList = topics.data ?? [];
  const selected = topicList.find((topic) => topic.id === topicId) ?? null;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm font-medium text-indigo-800 underline">
          All projects
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Typography.Title level={1} className="!mb-0">
            {project.data.title}
          </Typography.Title>
          {readOnly && <Tag>Archived</Tag>}
          <Link to={`/projects/${projectId}/import`} className="text-sm font-medium text-indigo-800 underline">
            Import and export
          </Link>
        </div>
        {project.data.description && (
          <Typography.Paragraph className="mt-2 break-words">{project.data.description}</Typography.Paragraph>
        )}
      </div>

      {readOnly && (
        <Alert
          type="info"
          title="This project is archived. Restore it from the projects list to make changes."
        />
      )}

      {(modules.isError || topics.isError) && (
        <Alert
          type="error"
          title="Could not load the modules and topics."
          action={
            <Button
              onClick={() => {
                void modules.refetch();
                void topics.refetch();
              }}
            >
              Try again
            </Button>
          }
        />
      )}

      {!readOnly && (
        <StructureManager
          projectId={projectId}
          modules={modules.data ?? []}
          topics={topicList}
          onTopicArchived={(id) => {
            if (id === topicId) setParams({});
          }}
        />
      )}

      <div className="grid gap-6 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <ProjectStructure
          projectId={projectId}
          modules={modules.data ?? []}
          topics={topicList}
          selectedTopicId={topicId}
          onSelectTopic={(id) => setParams({ topic: id })}
          readOnly={readOnly}
        />
        <ItemsPanel
          projectId={projectId}
          topicId={topicId}
          topicTitle={selected?.title ?? null}
          modules={modules.data ?? []}
          topics={topicList}
          readOnly={readOnly}
        />
      </div>
    </div>
  );
}
