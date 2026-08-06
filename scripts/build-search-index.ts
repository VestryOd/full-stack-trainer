/**
 * Build-time search index generator.
 *
 * The site is a fully static export (`output: 'export'`) — there is no server at
 * request time — so search must run in the browser against a prebuilt index.
 * This script reuses the same server-only content loaders the pages use, so every
 * indexed URL is guaranteed to be a page that actually gets statically generated
 * (all list routes derive `generateStaticParams` from TOPICS / COURSES).
 *
 * Output (per locale) under `public/search/`:
 *   - index.<locale>.json  — serialized MiniSearch inverted index (no stored bodies)
 *   - docs.<locale>.json   — lightweight display metadata (title, snippet, url, badges)
 *   - meta.json            — counts + payload sizes (raw / gzip / brotli)
 *
 * Run: `npx tsx scripts/build-search-index.ts` (wired into `prebuild` / `predev`).
 */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import MiniSearch from 'minisearch';

import { TOPICS, getTopicById } from '../src/constants/topics';
import { COURSES } from '../src/constants/courses';
import { getSlugsForTopic, getArticle } from '../src/lib/content';
import { getQuestionsByTopic } from '../src/lib/questions';
import { getTasksByTopic } from '../src/lib/tasks';
import { getSlugsForCourse, getChapter } from '../src/lib/courses';
import type { Locale } from '../src/types';
import {
  MINISEARCH_OPTIONS,
  SEARCH_FIELDS,
  SEARCH_ID_FIELD,
  type SearchDisplayDoc as DisplayDoc,
  type SearchType,
} from '../src/lib/search/config';

const LOCALES: Locale[] = ['en', 'ru'];
const OUT_DIR = path.join(process.cwd(), 'public', 'search');

/** Full document fed to MiniSearch (body/tags used only for matching, not shipped). */
interface IndexDoc {
  id: string;
  type: SearchType;
  title: string;
  body: string;
  tags: string; // space-joined for indexing; DisplayDoc keeps the array form
  topicId: string;
  topicLabel: string;
  difficulty?: string;
  url: string;
}

// ── text helpers ──────────────────────────────────────────────────────────

/** Strip markdown to plain prose. Per product decision, code blocks are removed
 *  (search prose, not backtick noise); inline-code text is kept (API names matter). */
function stripMarkdown(md: string): string {
  return md
    .replace(/<!--[\s\S]*?-->/g, ' ')        // HTML comments (incl. verified marker)
    .replace(/```[\s\S]*?```/g, ' ')          // fenced code blocks
    .replace(/~~~[\s\S]*?~~~/g, ' ')          // fenced code blocks (tilde)
    .replace(/`([^`]+)`/g, '$1')              // inline code → keep text
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')    // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')  // links → link text
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')       // headings
    .replace(/^\s{0,3}>\s?/gm, '')            // blockquotes
    .replace(/^\s{0,3}[-*+]\s+/gm, '')        // unordered list markers
    .replace(/^\s{0,3}\d+\.\s+/gm, '')        // ordered list markers
    .replace(/^[-:|\s]+$/gm, ' ')             // table separators / hr rules
    .replace(/[*_~]{1,3}/g, '')               // emphasis markers
    .replace(/\|/g, ' ')                      // table cell pipes
    .replace(/\s+/g, ' ')                     // collapse whitespace
    .trim();
}

function prettifySlug(slug: string): string {
  return slug
    .replace(/^\d+[-_]/, '')
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/** Prefer the article's first `# heading` (md files have no frontmatter title). */
function extractTitle(md: string, fallbackSlug: string): string {
  const m = md.match(/^\s{0,3}#\s+(.+?)\s*$/m);
  if (m) return m[1].replace(/[*_`]/g, '').trim();
  return prettifySlug(fallbackSlug);
}

function makeSnippet(body: string, max = 160): string {
  if (body.length <= max) return body;
  const cut = body.lastIndexOf(' ', max);
  return body.slice(0, cut > 40 ? cut : max).trim() + '…';
}

function pick(text: { en: string; ru?: string } | undefined, locale: Locale): string {
  if (!text) return '';
  return (locale === 'ru' ? text.ru : text.en) || text.en || text.ru || '';
}

// ── document collection ───────────────────────────────────────────────────

function collectDocs(locale: Locale): { index: IndexDoc[]; skippedOrphans: string[] } {
  const index: IndexDoc[] = [];
  const skippedOrphans: string[] = [];

  const labelFor = (topicId: string) => getTopicById(topicId)?.label ?? prettifySlug(topicId);

  // Theory — iterate TOPICS (the routing source of truth); skip topics without md.
  for (const topic of TOPICS) {
    for (const slug of getSlugsForTopic(topic.id, locale)) {
      const art = getArticle(topic.id, slug, locale);
      if (!art) continue;
      const body = stripMarkdown(art.content);
      if (!body) continue;
      index.push({
        id: `theory:${topic.id}:${slug}`,
        type: 'theory',
        title: extractTitle(art.content, slug),
        body,
        tags: '',
        topicId: topic.id,
        topicLabel: topic.label,
        url: `/theory/${topic.id}/${slug}/`,
      });
    }
  }

  // Questions — iterate TOPICS so URLs resolve; orphan json files get no page.
  for (const topic of TOPICS) {
    for (const q of getQuestionsByTopic(topic.id)) {
      const title = pick(q.question, locale);
      if (!title) continue;
      index.push({
        // q.id is not globally unique (some questions are filed under multiple
        // topic JSONs); scope by the topic whose page actually renders it.
        id: `question:${topic.id}:${q.id}`,
        type: 'question',
        title,
        body: stripMarkdown(pick(q.answer, locale)),
        tags: (q.tags ?? []).join(' '),
        topicId: topic.id,
        topicLabel: topic.label,
        difficulty: q.difficulty,
        url: `/questions/${topic.id}/?q=q-${q.id}`,
      });
    }
  }

  // Tasks — description + solution explanation (code fields intentionally excluded).
  for (const topic of TOPICS) {
    for (const t of getTasksByTopic(topic.id)) {
      const title = pick(t.title, locale);
      if (!title) continue;
      const prose = `${pick(t.description, locale)} ${pick(t.solutionExplanation, locale)}`;
      index.push({
        id: `task:${topic.id}:${t.id}`,
        type: 'task',
        title,
        body: stripMarkdown(prose),
        tags: (t.tags ?? []).join(' '),
        topicId: topic.id,
        topicLabel: topic.label,
        difficulty: t.difficulty,
        url: `/tasks/${topic.id}/${t.id}/`,
      });
    }
  }

  // Courses — markdown chapters, same treatment as theory.
  for (const course of COURSES) {
    for (const slug of getSlugsForCourse(course.id, locale)) {
      const chapter = getChapter(course.id, slug, locale);
      if (!chapter) continue;
      const body = stripMarkdown(chapter.content);
      if (!body) continue;
      index.push({
        id: `course:${course.id}:${slug}`,
        type: 'course',
        title: extractTitle(chapter.content, slug),
        body,
        tags: '',
        topicId: course.id,
        topicLabel: course.label,
        url: `/courses/${course.id}/${slug}/`,
      });
    }
  }

  // Report question/task json files that have no reachable TOPICS page (locale-agnostic).
  if (locale === 'en') {
    const topicIds = new Set(TOPICS.map((t) => t.id));
    for (const dir of ['questions', 'tasks']) {
      const p = path.join(process.cwd(), 'content', dir);
      if (!fs.existsSync(p)) continue;
      for (const f of fs.readdirSync(p).filter((x) => x.endsWith('.json'))) {
        const id = f.replace(/\.json$/, '');
        if (!topicIds.has(id)) skippedOrphans.push(`${dir}/${f}`);
      }
    }
  }

  return { index, skippedOrphans };
}

// ── build ─────────────────────────────────────────────────────────────────

function sizes(json: string) {
  const raw = Buffer.byteLength(json);
  const gzip = zlib.gzipSync(json).length;
  const brotli = zlib.brotliCompressSync(json).length;
  return { raw, gzip, brotli };
}

function kb(n: number) {
  return `${(n / 1024).toFixed(0)} KB`;
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const meta: Record<string, unknown> = { fields: SEARCH_FIELDS, idField: SEARCH_ID_FIELD, locales: {} };
  let orphans: string[] = [];

  console.log('Building search index…\n');
  console.log(
    ['locale', 'docs', 'index raw', 'index br', 'docs raw', 'docs br'].map((s) => s.padEnd(11)).join(''),
  );

  for (const locale of LOCALES) {
    const { index, skippedOrphans } = collectDocs(locale);
    if (skippedOrphans.length) orphans = skippedOrphans;

    const mini = new MiniSearch<IndexDoc>({
      ...MINISEARCH_OPTIONS,
      storeFields: [], // keep the shipped index lean — display data lives in docs.json
    });
    mini.addAll(index);

    const display: DisplayDoc[] = index.map((d) => ({
      id: d.id,
      type: d.type,
      title: d.title,
      snippet: makeSnippet(d.body),
      tags: d.tags ? d.tags.split(' ').filter(Boolean) : [],
      topicId: d.topicId,
      topicLabel: d.topicLabel,
      difficulty: d.difficulty,
      url: d.url,
    }));

    const indexJson = JSON.stringify(mini);
    const docsJson = JSON.stringify(display);
    fs.writeFileSync(path.join(OUT_DIR, `index.${locale}.json`), indexJson);
    fs.writeFileSync(path.join(OUT_DIR, `docs.${locale}.json`), docsJson);

    const iz = sizes(indexJson);
    const dz = sizes(docsJson);
    const byType = display.reduce<Record<string, number>>((acc, d) => {
      acc[d.type] = (acc[d.type] ?? 0) + 1;
      return acc;
    }, {});
    (meta.locales as Record<string, unknown>)[locale] = {
      docs: display.length,
      byType,
      index: iz,
      docsFile: dz,
    };

    console.log(
      [locale, String(display.length), kb(iz.raw), kb(iz.brotli), kb(dz.raw), kb(dz.brotli)]
        .map((s) => s.padEnd(11))
        .join(''),
    );
  }

  fs.writeFileSync(path.join(OUT_DIR, 'meta.json'), JSON.stringify(meta, null, 2));

  const en = (meta.locales as Record<string, { byType: Record<string, number> }>).en;
  console.log('\nBy type (en):', en.byType);
  if (orphans.length) {
    console.log(
      `\n⚠️  Orphan content files (no TOPICS id → no page, skipped): ${orphans.join(', ')}`,
    );
  }
  console.log(`\nWrote index + docs for [${LOCALES.join(', ')}] → ${path.relative(process.cwd(), OUT_DIR)}/`);
}

main();
