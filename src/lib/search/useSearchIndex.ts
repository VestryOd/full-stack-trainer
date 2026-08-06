'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import MiniSearch from 'minisearch';
import type { Locale } from '@/types';
import {
  MAX_RESULTS_PER_GROUP,
  MAX_RESULTS_TOTAL,
  MINISEARCH_OPTIONS,
  SEARCH_QUERY_OPTIONS,
  SEARCH_TYPE_ORDER,
  type SearchDisplayDoc,
  type SearchType,
} from './config';

interface LoadedIndex {
  mini: MiniSearch;
  docs: Map<string, SearchDisplayDoc>;
}

export interface SearchGroup {
  type: SearchType;
  hits: SearchDisplayDoc[];
}

export interface SearchOutcome {
  groups: SearchGroup[];
  flat: SearchDisplayDoc[]; // in display order — for keyboard navigation
  total: number;
  truncated: boolean;
}

/** Facet filter applied to results (type and/or topic). */
export interface SearchFilter {
  type?: SearchType | null;
  topicId?: string | null;
}

// Module-level cache so the index is fetched/parsed at most once per locale for
// the whole session, shared across every mount of the palette.
const cache = new Map<Locale, LoadedIndex>();
const inflight = new Map<Locale, Promise<LoadedIndex>>();

async function fetchJson(url: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`search: failed to load ${url} (${res.status})`);
  return res.text();
}

async function loadIndex(locale: Locale): Promise<LoadedIndex> {
  const cached = cache.get(locale);
  if (cached) return cached;
  const existing = inflight.get(locale);
  if (existing) return existing;

  const promise = (async () => {
    const [indexJson, docsJson] = await Promise.all([
      fetchJson(`/search/index.${locale}.json`),
      fetchJson(`/search/docs.${locale}.json`),
    ]);
    const mini = MiniSearch.loadJSON(indexJson, MINISEARCH_OPTIONS);
    const docs = new Map<string, SearchDisplayDoc>(
      (JSON.parse(docsJson) as SearchDisplayDoc[]).map((d) => [d.id, d]),
    );
    const loaded: LoadedIndex = { mini, docs };
    cache.set(locale, loaded);
    inflight.delete(locale);
    return loaded;
  })();

  inflight.set(locale, promise);
  return promise;
}

function group(docs: SearchDisplayDoc[]): SearchOutcome {
  const buckets = new Map<SearchType, SearchDisplayDoc[]>();
  let total = 0;
  let truncated = false;

  for (const doc of docs) {
    const bucket = buckets.get(doc.type) ?? [];
    if (bucket.length >= MAX_RESULTS_PER_GROUP) {
      truncated = true;
      continue;
    }
    if (total >= MAX_RESULTS_TOTAL) {
      truncated = true;
      break;
    }
    bucket.push(doc);
    buckets.set(doc.type, bucket);
    total += 1;
  }

  const groups: SearchGroup[] = SEARCH_TYPE_ORDER.filter((t) => buckets.has(t)).map((type) => ({
    type,
    hits: buckets.get(type)!,
  }));
  const flat = groups.flatMap((g) => g.hits);
  return { groups, flat, total, truncated };
}

/**
 * Lazily loads the active-locale index (only when `enabled` — i.e. the palette is
 * open) and exposes a synchronous `search`. Returns load status for the UI.
 */
export function useSearchIndex(locale: Locale, enabled: boolean) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>(
    cache.has(locale) ? 'ready' : 'idle',
  );
  const indexRef = useRef<LoadedIndex | null>(cache.get(locale) ?? null);

  useEffect(() => {
    if (!enabled) return;
    const ready = cache.get(locale);
    if (ready) {
      indexRef.current = ready;
      setStatus('ready');
      return;
    }
    let cancelled = false;
    setStatus('loading');
    loadIndex(locale)
      .then((loaded) => {
        if (cancelled) return;
        indexRef.current = loaded;
        setStatus('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        console.error(err);
        setStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [locale, enabled]);

  const search = useCallback((query: string, filter?: SearchFilter): SearchOutcome => {
    const idx = indexRef.current;
    const q = query.trim();
    if (!idx || q.length < 2) return { groups: [], flat: [], total: 0, truncated: false };
    const raw = idx.mini.search(q, SEARCH_QUERY_OPTIONS);
    const docs: SearchDisplayDoc[] = [];
    for (const r of raw) {
      const doc = idx.docs.get(r.id as string);
      if (!doc) continue;
      if (filter?.type && doc.type !== filter.type) continue;
      if (filter?.topicId && doc.topicId !== filter.topicId) continue;
      docs.push(doc);
    }
    return group(docs);
  }, []);

  return { status, search };
}
