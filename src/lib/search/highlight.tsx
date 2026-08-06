import type { ReactNode } from 'react';

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Split `query` into searchable terms (≥2 chars, lowercased, regex-escaped). */
export function queryTerms(query: string): string[] {
  return query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length >= 2)
    .map(escapeRegExp);
}

/** Wrap occurrences of the query terms in `<mark>` for rendering plain React text. */
export function highlightText(text: string, query: string): ReactNode {
  const terms = queryTerms(query);
  if (!terms.length) return text;
  const re = new RegExp(`(${terms.join('|')})`, 'ig');
  return text.split(re).map((part, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="search-hl">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}
