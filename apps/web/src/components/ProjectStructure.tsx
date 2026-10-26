import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Form, Input, Select, Tree, Typography } from "antd";
import { useState } from "react";

import { api } from "../api/client";
import type { ModuleDto, TopicDto } from "../api/types";
import { describeError } from "../errors";

interface Props {
  projectId: string;
  modules: ModuleDto[];
  topics: TopicDto[];
  selectedTopicId: string | null;
  onSelectTopic: (topicId: string) => void;
  readOnly: boolean;
}

const TOPIC_PREFIX = "t:";

export function ProjectStructure({
  projectId,
  modules,
  topics,
  selectedTopicId,
  onSelectTopic,
  readOnly,
}: Props) {
  const queryClient = useQueryClient();
  const [moduleTitle, setModuleTitle] = useState("");
  const [moduleError, setModuleError] = useState<string | null>(null);
  const [topicTitle, setTopicTitle] = useState("");
  const [topicModule, setTopicModule] = useState<string | null>(null);
  const [topicError, setTopicError] = useState<string | null>(null);

  const addModule = useMutation({
    mutationFn: (title: string) => api.post(`/api/v1/projects/${projectId}/modules`, { title }),
    onSuccess: async () => {
      setModuleTitle("");
      setModuleError(null);
      await queryClient.invalidateQueries({ queryKey: ["modules", projectId] });
    },
    onError: (error) =>
      setModuleError(describeError(error, "Could not add the module. Please try again.")),
  });

  const addTopic = useMutation({
    mutationFn: (input: { module_id: string; title: string }) =>
      api.post(`/api/v1/projects/${projectId}/topics`, input),
    onSuccess: async () => {
      setTopicTitle("");
      setTopicError(null);
      await queryClient.invalidateQueries({ queryKey: ["topics", projectId] });
    },
    onError: (error) =>
      setTopicError(describeError(error, "Could not add the topic. Please try again.")),
  });

  function submitModule() {
    const title = moduleTitle.trim();
    if (title === "") {
      setModuleError("Enter a module title.");
      return;
    }
    setModuleError(null);
    addModule.mutate(title);
  }

  function submitTopic() {
    const title = topicTitle.trim();
    if (topicModule === null) {
      setTopicError("Choose a module first.");
      return;
    }
    if (title === "") {
      setTopicError("Enter a topic title.");
      return;
    }
    setTopicError(null);
    addTopic.mutate({ module_id: topicModule, title });
  }

  const treeData = modules.map((module) => ({
    key: `m:${module.id}`,
    title: module.title,
    selectable: false,
    children: topics
      .filter((topic) => topic.module_id === module.id)
      .map((topic) => ({ key: `${TOPIC_PREFIX}${topic.id}`, title: topic.title, isLeaf: true })),
  }));

  return (
    <div className="space-y-6">
      <section aria-labelledby="structure-heading">
        <Typography.Title level={2} id="structure-heading" className="!text-xl">
          Modules and topics
        </Typography.Title>
        {modules.length === 0 ? (
          <Typography.Paragraph>No modules yet. Add one below.</Typography.Paragraph>
        ) : (
          <Tree
            // Re-created when modules or topics change, so a new topic is never hidden inside a
            // collapsed module (a module without topics starts out collapsed).
            key={`${modules.map((m) => m.id).join(",")}|${topics.map((t) => t.id).join(",")}`}
            defaultExpandAll
            blockNode
            treeData={treeData}
            selectedKeys={selectedTopicId ? [`${TOPIC_PREFIX}${selectedTopicId}`] : []}
            onSelect={(_keys, info) => {
              const key = String(info.node.key);
              if (key.startsWith(TOPIC_PREFIX)) onSelectTopic(key.slice(TOPIC_PREFIX.length));
            }}
          />
        )}
      </section>

      <Form layout="vertical" onFinish={submitModule} noValidate requiredMark={false}>
        <Form.Item label="New module title" htmlFor="new-module-title" className="!mb-2">
          <Input
            id="new-module-title"
            maxLength={200}
            disabled={readOnly}
            value={moduleTitle}
            onChange={(event) => setModuleTitle(event.target.value)}
            status={moduleError ? "error" : undefined}
            aria-invalid={moduleError !== null}
            aria-describedby={moduleError ? "module-error" : undefined}
          />
        </Form.Item>
        {moduleError && (
          <Alert id="module-error" type="error" title={moduleError} className="mb-2" />
        )}
        <Button htmlType="submit" disabled={readOnly || addModule.isPending}>
          Add module
        </Button>
      </Form>

      <Form layout="vertical" onFinish={submitTopic} noValidate requiredMark={false}>
        <Form.Item label="Module" htmlFor="topic-module" className="!mb-2">
          <Select
            id="topic-module"
            aria-label="Module for the new topic"
            placeholder="Choose a module"
            virtual={false}
            disabled={readOnly}
            value={topicModule}
            onChange={setTopicModule}
            options={modules.map((module) => ({ value: module.id, label: module.title }))}
          />
        </Form.Item>
        <Form.Item label="New topic title" htmlFor="new-topic-title" className="!mb-2">
          <Input
            id="new-topic-title"
            maxLength={200}
            disabled={readOnly}
            value={topicTitle}
            onChange={(event) => setTopicTitle(event.target.value)}
            status={topicError ? "error" : undefined}
            aria-invalid={topicError !== null}
            aria-describedby={topicError ? "topic-error" : undefined}
          />
        </Form.Item>
        {topicError && <Alert id="topic-error" type="error" title={topicError} className="mb-2" />}
        <Button htmlType="submit" disabled={readOnly || addTopic.isPending}>
          Add topic
        </Button>
      </Form>
    </div>
  );
}
