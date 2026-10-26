import { api } from "./client";
import type { PageDto } from "./types";

const PAGE_SIZE = 100;
// A safety bound so a misbehaving server cannot make the browser loop forever.
const MAX_PAGES = 10;

/** Follows the cursor until the list is complete (or the safety bound is reached). */
export async function fetchAll<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const result: PageDto<T> = await api.get<PageDto<T>>(path, { limit: PAGE_SIZE, cursor });
    items.push(...result.items);
    cursor = result.next_cursor;
    if (cursor === null) break;
  }
  return items;
}
