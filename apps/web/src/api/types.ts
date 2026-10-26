/** Shapes returned by the content API (see docs/api/content-api.md). */

export interface ProjectDto {
  id: string;
  title: string;
  description: string | null;
  archived: boolean;
}

export interface ModuleDto {
  id: string;
  project_id: string;
  title: string;
  archived: boolean;
}

export interface TopicDto {
  id: string;
  project_id: string;
  module_id: string;
  title: string;
  archived: boolean;
}

export const ITEM_TYPES = ["question", "phrase", "vocabulary", "concept", "scenario"] as const;
export type ItemType = (typeof ITEM_TYPES)[number];

export interface ItemDto {
  id: string;
  project_id: string;
  topic_id: string;
  type: ItemType;
  prompt: string;
  sample_answer: string | null;
  translation: string | null;
  keywords: string[];
  tags: string[];
  follow_up_questions: string[];
  difficulty: number | null;
  archived: boolean;
}

export interface PageDto<T> {
  items: T[];
  next_cursor: string | null;
}
