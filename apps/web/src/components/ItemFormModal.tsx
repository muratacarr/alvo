import { Alert, Button, Form, Input, InputNumber, Modal, Radio } from "antd";
import { useEffect } from "react";

import { ITEM_TYPES, type ItemDto, type ItemType } from "../api/types";

interface FormValues {
  type: ItemType;
  prompt: string;
  sample_answer: string;
  translation: string;
  keywords: string;
  tags: string;
  difficulty: number | null;
}

export type ItemPayload = Record<string, unknown>;

interface Props {
  open: boolean;
  /** The topic a new item is added to. */
  topicId: string;
  /** The item being edited, or null when adding a new one. */
  item: ItemDto | null;
  error: string | null;
  saving: boolean;
  onCancel: () => void;
  /** Receives only what must be sent: everything for a new item, only changes for an edit. */
  onSubmit: (payload: ItemPayload) => void;
}

const EMPTY: FormValues = {
  type: "question",
  prompt: "",
  sample_answer: "",
  translation: "",
  keywords: "",
  tags: "",
  difficulty: null,
};

export function parseList(text: string): string[] {
  const seen = new Set<string>();
  for (const part of text.split(",")) {
    const value = part.trim();
    if (value !== "") seen.add(value);
  }
  return [...seen];
}

function toFormValues(item: ItemDto | null): FormValues {
  if (item === null) return EMPTY;
  return {
    type: item.type,
    prompt: item.prompt,
    sample_answer: item.sample_answer ?? "",
    translation: item.translation ?? "",
    keywords: item.keywords.join(", "),
    tags: item.tags.join(", "),
    difficulty: item.difficulty,
  };
}

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((v, i) => v === b[i]);

/** What to send for an existing item: only the fields the user actually changed. */
export function changesFor(item: ItemDto, values: FormValues): ItemPayload {
  const changes: ItemPayload = {};
  const prompt = values.prompt.trim();
  if (values.type !== item.type) changes.type = values.type;
  if (prompt !== item.prompt) changes.prompt = prompt;
  const answer = values.sample_answer.trim();
  if (answer !== (item.sample_answer ?? "")) changes.sample_answer = answer === "" ? null : answer;
  const translation = values.translation.trim();
  if (translation !== (item.translation ?? "")) changes.translation = translation === "" ? null : translation;
  const keywords = parseList(values.keywords);
  if (!sameList(keywords, item.keywords)) changes.keywords = keywords;
  const tags = parseList(values.tags);
  if (!sameList(tags, item.tags)) changes.tags = tags;
  if ((values.difficulty ?? null) !== item.difficulty) changes.difficulty = values.difficulty ?? null;
  return changes;
}

/** What to send for a new item: required fields plus those the user filled in. */
export function payloadForNew(topicId: string, values: FormValues): ItemPayload {
  const payload: ItemPayload = { topic_id: topicId, type: values.type, prompt: values.prompt.trim() };
  if (values.sample_answer.trim() !== "") payload.sample_answer = values.sample_answer.trim();
  if (values.translation.trim() !== "") payload.translation = values.translation.trim();
  const keywords = parseList(values.keywords);
  if (keywords.length > 0) payload.keywords = keywords;
  const tags = parseList(values.tags);
  if (tags.length > 0) payload.tags = tags;
  if (values.difficulty !== null && values.difficulty !== undefined) payload.difficulty = values.difficulty;
  return payload;
}

export function ItemFormModal({ open, topicId, item, error, saving, onCancel, onSubmit }: Props) {
  const [form] = Form.useForm<FormValues>();

  useEffect(() => {
    if (open) form.setFieldsValue(toFormValues(item));
  }, [open, item, form]);

  return (
    <Modal
      open={open}
      title={item ? "Edit item" : "Add item"}
      footer={null}
      onCancel={onCancel}
      destroyOnHidden
    >
      <Form<FormValues>
        form={form}
        layout="vertical"
        initialValues={toFormValues(item)}
        requiredMark={false}
        noValidate
        onFinish={(values) => {
          if (item) onSubmit(changesFor(item, values));
          else onSubmit(payloadForNew(topicId, values));
        }}
      >
        <Form.Item label="Type" name="type">
          <Radio.Group
            options={ITEM_TYPES.map((t) => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) }))}
          />
        </Form.Item>
        <Form.Item
          label="Prompt"
          name="prompt"
          rules={[{ required: true, whitespace: true, message: "Enter a prompt." }]}
        >
          <Input.TextArea maxLength={2000} rows={3} />
        </Form.Item>
        <Form.Item label="Sample answer (optional)" name="sample_answer">
          <Input.TextArea maxLength={10000} rows={4} />
        </Form.Item>
        <Form.Item label="Translation (optional)" name="translation">
          <Input maxLength={2000} />
        </Form.Item>
        <Form.Item label="Keywords (comma separated, optional)" name="keywords">
          <Input />
        </Form.Item>
        <Form.Item label="Tags (comma separated, optional)" name="tags">
          <Input />
        </Form.Item>
        <Form.Item label="Difficulty (1-5, optional)" name="difficulty">
          <InputNumber min={1} max={5} precision={0} />
        </Form.Item>
        {error && <Alert type="error" title={error} className="mb-4" />}
        <div className="flex gap-2">
          <Button type="primary" htmlType="submit" disabled={saving}>
            {saving ? "Saving…" : "Save item"}
          </Button>
          <Button onClick={onCancel}>Cancel</Button>
        </div>
      </Form>
    </Modal>
  );
}
