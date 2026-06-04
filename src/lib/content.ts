import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import type { TheoryArticle, Locale } from '@/types';

const CONTENT_DIR = path.join(process.cwd(), 'content', 'topics');

function topicFolderName(topicId: string): string {
  const map: Record<string, string> = {
    graphql:         'graphql',
    nextjs:          'nextjs',
    nodejs:          'nodejs',
    postgresql:      'postgresql',
    prisma:          'prisma',
    nestjs:          'nestjs',
    javascript:      'javascript',
    typescript:      'typescript',
    react:           'react',
    'css-html':      'css-html',
    'web-performance': 'web-performance',
    'browser-runtime': 'browser-runtime',
    'http-rest':     'http-rest',
    testing:         'testing',
    security:        'security',
    'solid-grasp':   'solid-grasp',
    'oop-patterns':  'oop-patterns',
    algorithms:      'algorithms',
    'system-design': 'system-design',
    architecture:    'architecture',
    git:             'git',
    'ci-cd':         'ci-cd',
    docker:          'docker',
    bundlers:        'bundlers',
    ddd:             'ddd',
    tdd:             'tdd',
    'event-driven':  'event-driven',
  };
  return map[topicId] ?? topicId;
}

export function getArticlesForTopic(topicId: string, locale: Locale): TheoryArticle[] {
  const folder = topicFolderName(topicId);
  const dir = path.join(CONTENT_DIR, folder, locale);

  if (!fs.existsSync(dir)) return [];

  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.md'));

  return files
    .map((file) => {
      const raw = fs.readFileSync(path.join(dir, file), 'utf-8');
      const { data, content } = matter(raw);
      const slug = file.replace(/\.md$/, '');
      const title = (data.title as string | undefined) ?? slug;
      return { topicId, slug, title, content, locale };
    })
    .sort((a, b) => a.slug.localeCompare(b.slug));
}

export function getArticle(topicId: string, slug: string, locale: Locale): TheoryArticle | null {
  const folder = topicFolderName(topicId);
  const filePath = path.join(CONTENT_DIR, folder, locale, `${slug}.md`);

  if (!fs.existsSync(filePath)) return null;

  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const title = (data.title as string | undefined) ?? slug;
  return { topicId, slug, title, content, locale };
}

export function getTopicsWithContent(): string[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  return fs.readdirSync(CONTENT_DIR).filter((name) => {
    const stat = fs.statSync(path.join(CONTENT_DIR, name));
    return stat.isDirectory();
  });
}

export function getSlugsForTopic(topicId: string, locale: Locale): string[] {
  const folder = topicFolderName(topicId);
  const dir = path.join(CONTENT_DIR, folder, locale);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.md'))
    .map((f) => f.replace(/\.md$/, ''));
}
