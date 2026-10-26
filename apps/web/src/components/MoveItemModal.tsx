import { Alert, Button, Modal, Select } from "antd";
import { useState } from "react";

import type { ItemDto, ModuleDto, TopicDto } from "../api/types";

interface Props {
  item: ItemDto;
  modules: ModuleDto[];
  topics: TopicDto[];
  error: string | null;
  saving: boolean;
  onCancel: () => void;
  onSubmit: (topicId: string) => void;
}

/** Every topic an item can move to: live topics of live modules, except where it already is. */
export function moveTargets(item: ItemDto, modules: ModuleDto[], topics: TopicDto[]) {
  const titles = new Map(modules.map((module) => [module.id, module.title]));
  return topics
    .filter((topic) => topic.id !== item.topic_id && titles.has(topic.module_id))
    .map((topic) => ({ value: topic.id, label: `${titles.get(topic.module_id)} › ${topic.title}` }));
}

export function MoveItemModal({ item, modules, topics, error, saving, onCancel, onSubmit }: Props) {
  const [target, setTarget] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  function submit() {
    if (target === null) {
      setProblem("Choose a topic.");
      return;
    }
    setProblem(null);
    onSubmit(target);
  }

  return (
    <Modal open title="Move item" footer={null} onCancel={onCancel} destroyOnHidden>
      <div className="space-y-3">
        <p className="break-words">{item.prompt}</p>
        <div className="flex flex-col gap-1">
          <label htmlFor="move-target" className="font-medium">
            Move to topic
          </label>
          <Select
            id="move-target"
            aria-label="Move to topic"
            placeholder="Choose a topic"
            virtual={false}
            value={target}
            onChange={setTarget}
            options={moveTargets(item, modules, topics)}
            status={problem ? "error" : undefined}
          />
          {problem && <p className="text-red-800">{problem}</p>}
        </div>
        {error && <Alert type="error" title={error} />}
        <div className="flex gap-2">
          <Button type="primary" disabled={saving} onClick={submit}>
            {saving ? "Moving…" : "Move"}
          </Button>
          <Button onClick={onCancel}>Cancel</Button>
        </div>
      </div>
    </Modal>
  );
}
