import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, List, Tag, Typography } from "antd";
import { useState } from "react";

import { api } from "../api/client";
import type { ItemDto, PageDto } from "../api/types";
import { describeError } from "../errors";
import { ItemFormModal, type ItemPayload } from "./ItemFormModal";

interface Props {
  projectId: string;
  topicId: string | null;
  topicTitle: string | null;
  readOnly: boolean;
}

const PAGE_SIZE = 50;
const LABEL_LENGTH = 60;

/** Short, readable name for buttons, so screen readers say which item an action is for. */
const clip = (text: string) => (text.length > LABEL_LENGTH ? `${text.slice(0, LABEL_LENGTH)}…` : text);

export function ItemsPanel({ projectId, topicId, topicTitle, readOnly }: Props) {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [dialog, setDialog] = useState<{ item: ItemDto | null } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const items = useInfiniteQuery({
    queryKey: ["items", projectId, topicId, { showArchived }],
    enabled: topicId !== null,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      api.get<PageDto<ItemDto>>(`/api/v1/projects/${projectId}/items`, {
        topic_id: topicId,
        limit: PAGE_SIZE,
        cursor: pageParam,
        include_archived: showArchived ? true : undefined,
      }),
    getNextPageParam: (last) => last.next_cursor,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["items", projectId] });

  const save = useMutation({
    mutationFn: ({ item, payload }: { item: ItemDto | null; payload: ItemPayload }) =>
      item
        ? api.patch(`/api/v1/projects/${projectId}/items/${item.id}`, payload)
        : api.post(`/api/v1/projects/${projectId}/items`, payload),
    onSuccess: async () => {
      setDialog(null);
      setSaveError(null);
      await refresh();
    },
    onError: (error) => setSaveError(describeError(error, "Could not save the item. Please try again.")),
  });

  const archive = useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/projects/${projectId}/items/${id}`),
    onSuccess: refresh,
  });

  if (topicId === null) {
    return <Typography.Paragraph>Select a topic to see its items.</Typography.Paragraph>;
  }

  const entries = items.data?.pages.flatMap((page) => page.items) ?? [];

  function openDialog(item: ItemDto | null) {
    setSaveError(null);
    setDialog({ item });
  }

  function submit(item: ItemDto | null, payload: ItemPayload) {
    if (item && Object.keys(payload).length === 0) {
      setDialog(null); // nothing changed: no request
      return;
    }
    save.mutate({ item, payload });
  }

  return (
    <section aria-labelledby="items-heading">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <Typography.Title level={2} id="items-heading" className="!mb-0 !text-xl">
          {topicTitle ?? "Items"}
        </Typography.Title>
        <div className="flex flex-wrap items-center gap-3">
          <Checkbox checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)}>
            Show archived items
          </Checkbox>
          {!readOnly && (
            <Button type="primary" onClick={() => openDialog(null)}>
              Add item
            </Button>
          )}
        </div>
      </div>

      {archive.error && (
        <Alert
          type="error"
          title={describeError(archive.error, "That change could not be saved. Please try again.")}
          className="mb-3"
        />
      )}
      {items.isPending && (
        <p role="status" className="text-slate-700">
          Loading items…
        </p>
      )}
      {items.isError && (
        <Alert
          type="error"
          title={describeError(items.error, "Could not load items.")}
          action={<Button onClick={() => void items.refetch()}>Try again</Button>}
        />
      )}
      {items.isSuccess && entries.length === 0 && (
        <Typography.Paragraph>No items in this topic yet.</Typography.Paragraph>
      )}

      {entries.length > 0 && (
        <List
          bordered
          dataSource={entries}
          renderItem={(entry) => (
            <List.Item key={entry.id}>
              <div className="flex w-full flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <Typography.Text strong className="break-words">
                    {entry.prompt}
                  </Typography.Text>
                  <div className="flex flex-wrap gap-1">
                    <Tag>{entry.type}</Tag>
                    {entry.difficulty !== null && <Tag>Difficulty {entry.difficulty}</Tag>}
                    {entry.archived && <Tag>Archived</Tag>}
                    {entry.keywords.map((keyword) => (
                      <Tag key={`k-${keyword}`}>{keyword}</Tag>
                    ))}
                    {entry.tags.map((tag) => (
                      <Tag key={`t-${tag}`}>{tag}</Tag>
                    ))}
                  </div>
                  {entry.sample_answer && (
                    <Typography.Paragraph className="!mb-0 break-words">
                      {entry.sample_answer}
                    </Typography.Paragraph>
                  )}
                  {entry.translation && (
                    <Typography.Paragraph type="secondary" className="!mb-0 break-words">
                      {entry.translation}
                    </Typography.Paragraph>
                  )}
                </div>
                {!readOnly && !entry.archived && (
                  <div className="flex gap-2">
                    <Button aria-label={`Edit ${clip(entry.prompt)}`} onClick={() => openDialog(entry)}>
                      Edit
                    </Button>
                    <Button
                      aria-label={`Archive ${clip(entry.prompt)}`}
                      onClick={() => archive.mutate(entry.id)}
                    >
                      Archive
                    </Button>
                  </div>
                )}
              </div>
            </List.Item>
          )}
        />
      )}

      {items.hasNextPage && (
        <Button
          className="mt-4"
          disabled={items.isFetchingNextPage}
          onClick={() => void items.fetchNextPage()}
        >
          {items.isFetchingNextPage ? "Loading…" : "Load more"}
        </Button>
      )}

      <ItemFormModal
        open={dialog !== null}
        topicId={topicId}
        item={dialog?.item ?? null}
        error={saveError}
        saving={save.isPending}
        onCancel={() => setDialog(null)}
        onSubmit={(payload) => submit(dialog?.item ?? null, payload)}
      />
    </section>
  );
}
