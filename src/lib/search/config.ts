/**
 * Shared search configuration — imported by BOTH the build-time index generator
 * (`scripts/build-search-index.ts`) and the client loader, so index shape and
 * query options can never drift apart. Must stay dependency-free / client-safe.
 */
import type { Options as MiniSearchOptions, SearchOptions } from 'minisearch';

export type SearchType = 'theory' | 'question' | 'task' | 'course';

/** Fields MiniSearch indexes. */
export const SEARCH_FIELDS = ['title', 'body', 'tags'] as const;
export const SEARCH_ID_FIELD = 'id';

/** Options passed to `new MiniSearch()` (build) and `MiniSearch.loadJSON()` (client). */
export const MINISEARCH_OPTIONS: Pick<MiniSearchOptions, 'idField' | 'fields'> = {
  idField: SEARCH_ID_FIELD,
  fields: [...SEARCH_FIELDS],
};

/** Query options: require all terms (AND), tolerate typos, prefer titles/tags. */
export const SEARCH_QUERY_OPTIONS: SearchOptions = {
  prefix: true,
  fuzzy: 0.2,
  combineWith: 'AND',
  boost: { title: 3, tags: 2, body: 1 },
};

/** Display document shipped to the client (no body — matching lives in the index). */
export interface SearchDisplayDoc {
  id: string;
  type: SearchType;
  title: string;
  snippet: string;
  tags: string[];
  topicId: string;
  topicLabel: string;
  difficulty?: string;
  url: string;
}

/** Route-derived scope used to pre-filter the palette when opened on a section page. */
export interface SearchScope {
  type: SearchType | null;
  topicId: string | null;
  topicLabel: string | null;
}

/** Result-group order and their i18n label keys (resolved via `t2`). */
export const SEARCH_TYPE_ORDER: SearchType[] = ['theory', 'question', 'task', 'course'];
export const SEARCH_TYPE_LABEL_KEY: Record<SearchType, string> = {
  theory: 'search.type.theory',
  question: 'search.type.question',
  task: 'search.type.task',
  course: 'search.type.course',
};

/** Cap results so a huge match set never janks the palette. */
export const MAX_RESULTS_PER_GROUP = 8;
export const MAX_RESULTS_TOTAL = 40;
