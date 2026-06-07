# PROMPT 1 — Project Scaffold & Configuration

> Run this prompt in the `full-stack-trainer/` directory.
> This prompt sets up the entire Next.js project structure, configuration, and static export for Netlify.

---

## YOUR ROLE

You are a senior fullstack engineer setting up a production-ready Next.js 14 application.
Build everything completely — no placeholders, no TODOs. Every file must be functional.

---

## PROJECT OVERVIEW

Build a **Full-Stack Interview Trainer** — a static website for senior fullstack developer interview preparation.

**Stack:**
- Next.js 14 (App Router, static export — `output: 'export'`)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- `shiki` for syntax highlighting (static, zero client JS)
- `next-mdx-remote` for rendering `.md` files
- Deployment target: Netlify (static)

---

## EXISTING CONTENT

The project already has a `topics/` directory with this structure:
```
topics/
  GraphQL/
    ru/           ← markdown files in Russian (created by ChatGPT, need verification)
  Next.js/
    ru/
  Node.js/
    ru/
  PostgreSQL/
    ru/
  Prisma ORM/
    ru/
  Strapi/
    ru/
```

**Your job in this prompt:** scaffold the project, NOT generate content. Content comes in Prompt 2.

---

## FULL TOPIC LIST

These are all topics the site will cover. Use this list everywhere (navigation, types, constants):

```typescript
export const TOPICS = [
  // Deep coverage
  { id: 'javascript',       label: 'JavaScript',              level: 'deep' },
  { id: 'typescript',       label: 'TypeScript Advanced',     level: 'deep' },
  { id: 'react',            label: 'React',                   level: 'deep' },
  { id: 'nextjs',           label: 'Next.js',                 level: 'deep' },
  { id: 'nodejs',           label: 'Node.js',                 level: 'deep' },
  // Medium coverage
  { id: 'nestjs',           label: 'Nest.js',                 level: 'medium' },
  { id: 'postgresql',       label: 'PostgreSQL',              level: 'medium' },
  { id: 'prisma',           label: 'Prisma ORM',              level: 'medium' },
  { id: 'graphql',          label: 'GraphQL',                 level: 'medium' },
  { id: 'css-html',         label: 'CSS + HTML Advanced',     level: 'medium' },
  { id: 'web-performance',  label: 'Web Performance',         level: 'medium' },
  { id: 'browser-runtime',  label: 'Browser / JS Runtime',   level: 'medium' },
  { id: 'http-rest',        label: 'HTTP / REST',             level: 'medium' },
  { id: 'testing',          label: 'Testing',                 level: 'medium' },
  { id: 'security',         label: 'Security',                level: 'medium' },
  { id: 'solid-grasp',      label: 'SOLID + GRASP',          level: 'medium' },
  { id: 'oop-patterns',     label: 'OOP Patterns (GoF)',      level: 'medium' },
  { id: 'algorithms',       label: 'Algorithms & DS',         level: 'medium' },
  { id: 'system-design',    label: 'System Design',          level: 'medium' },
  { id: 'architecture',     label: 'Architecture Patterns',  level: 'medium' },
  // Light coverage
  { id: 'git',              label: 'Git + Git Flow',          level: 'light' },
  { id: 'ci-cd',            label: 'CI/CD',                   level: 'light' },
  { id: 'docker',           label: 'Docker',                  level: 'light' },
  { id: 'bundlers',         label: 'Webpack / Vite',          level: 'light' },
  { id: 'ddd',              label: 'DDD (Basics)',            level: 'light' },
  { id: 'tdd',              label: 'TDD',                     level: 'light' },
  { id: 'event-driven',     label: 'Event-Driven / CQRS',    level: 'light' },
] as const;
```

---

## DATA STRUCTURES

Define TypeScript interfaces in `src/types/index.ts`:

```typescript
// Locales
export type Locale = 'en' | 'ru';

// Topics
export type TopicLevel = 'deep' | 'medium' | 'light';

export interface Topic {
  id: string;
  label: string;
  level: TopicLevel;
}

// Theory content (from .md files)
export interface TheoryArticle {
  topicId: string;
  slug: string;
  title: string;
  content: string; // raw markdown
  locale: Locale;
}

// Questions
export type QuestionDifficulty = 'junior' | 'middle' | 'senior' | 'advanced';

export interface Question {
  id: string;
  topicId: string;
  difficulty: QuestionDifficulty;
  question: { en: string; ru: string };
  answer: { en: string; ru: string };  // may contain markdown with code blocks
  tags: string[];
}

// Tasks (coding challenges)
export type TaskDifficulty = 'easy' | 'medium' | 'hard';

export interface Task {
  id: string;
  topicId: string;
  difficulty: TaskDifficulty;
  title: { en: string; ru: string };
  description: { en: string; ru: string };
  starterCode?: string;           // language: typescript or javascript
  solution: string;               // code string
  solutionExplanation: { en: string; ru: string };
  tags: string[];
}

// Quiz
export interface QuizQuestion {
  id: string;
  topicId: string;
  question: { en: string; ru: string };
  options: { en: string[]; ru: string[] };  // 4 options
  correctIndex: number;
  explanation: { en: string; ru: string };
}
```

---

## CONTENT FILE STRUCTURE

All content lives in `content/` at the project root:

```
content/
  topics/           ← copy of existing topics/ folder, all markdown
    graphql/
      ru/
        *.md
      en/           ← to be generated in Prompt 2
        *.md
    nextjs/
      ru/
      en/
    nodejs/
      ru/
      en/
    postgresql/
      ru/
      en/
    prisma/
      ru/
      en/
    ... (all other topics)
  questions/
    javascript.json
    typescript.json
    react.json
    nextjs.json
    nodejs.json
    nestjs.json
    postgresql.json
    prisma.json
    graphql.json
    css-html.json
    web-performance.json
    browser-runtime.json
    http-rest.json
    testing.json
    security.json
    solid-grasp.json
    oop-patterns.json
    algorithms.json
    system-design.json
    architecture.json
    git.json
    ci-cd.json
    docker.json
    bundlers.json
    ddd.json
    tdd.json
    event-driven.json
  tasks/
    javascript.json
    typescript.json
    react.json
    nodejs.json
    algorithms.json
    css-html.json
    ... (topics where coding tasks make sense)
  quiz/
    javascript.json
    react.json
    typescript.json
    nodejs.json
    ... (one JSON per topic, array of QuizQuestion)
```

**In this prompt:** create the directory structure and empty JSON files with correct schema (empty arrays `[]`).
Copy existing `topics/` content into `content/topics/` preserving folder structure.

---

## SITE STRUCTURE & ROUTING

```
src/app/
  layout.tsx                          ← root layout, font, theme
  page.tsx                            ← home / dashboard
  theory/
    page.tsx                          ← topic list, pick a topic
    [topicId]/
      page.tsx                        ← article list for topic
      [slug]/
        page.tsx                      ← single article, rendered MD
  questions/
    page.tsx                          ← topic selector + question list
    [topicId]/
      page.tsx                        ← all questions for topic
  quiz/
    page.tsx                          ← quiz config (topic filter, count)
    [sessionId]/
      page.tsx                        ← active quiz session
  tasks/
    page.tsx                          ← task browser with filters
    [topicId]/
      [taskId]/
        page.tsx                      ← single task with hidden solution
```

---

## NAVIGATION

Top navigation bar with:
- Logo: "FST" (Full Stack Trainer)
- Links: Theory | Questions | Quiz | Tasks
- Locale switcher: EN | RU toggle (saves to localStorage)
- Theme toggle: Light / Dark (saves to localStorage)

---

## LOCALE SYSTEM

Implement a simple locale context — NO external i18n library:

```typescript
// src/context/LocaleContext.tsx
'use client';
import { createContext, useContext, useState, useEffect } from 'react';
import type { Locale } from '@/types';

interface LocaleContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (obj: { en: string; ru: string }) => string;
}

export const LocaleContext = createContext<LocaleContextValue>(...);

export function LocaleProvider({ children }) {
  // persist to localStorage key 'fst-locale'
  // default: 'en'
}

export const useLocale = () => useContext(LocaleContext);
```

The `t()` helper takes a bilingual object `{ en: string; ru: string }` and returns the string for current locale.

For theory markdown articles: show a language toggle **on the article page** that switches between `ru/` and `en/` markdown files for the same slug, without full page navigation.

---

## DATA LOADERS

Create utility functions in `src/lib/`:

```
src/lib/
  content.ts      ← reads markdown files from content/topics/
  questions.ts    ← reads + merges question JSONs, provides getByTopic(), getAll(), getRandom(n)
  tasks.ts        ← same pattern for tasks
  quiz.ts         ← same pattern for quiz questions
  highlight.ts    ← shiki syntax highlighter setup (server-side only)
```

All functions must be **server-side only** (no 'use client') — called in Server Components or `generateStaticParams`.

---

## KEY COMPONENTS

Scaffold these components (implementation can be minimal stubs — full UI in Prompt 3):

```
src/components/
  layout/
    Navbar.tsx
    Footer.tsx
    LocaleSwitcher.tsx
    ThemeToggle.tsx
  ui/                          ← shadcn/ui components go here (Button, Card, Badge, etc.)
  theory/
    ArticleRenderer.tsx        ← renders markdown with shiki code blocks
    ArticleCard.tsx
  questions/
    QuestionCard.tsx           ← question title visible, answer hidden under spoiler
    QuestionList.tsx
    DifficultyBadge.tsx
  quiz/
    QuizCard.tsx               ← multiple choice, 4 options
    QuizProgress.tsx
    QuizResult.tsx
  tasks/
    TaskCard.tsx               ← title + description visible, solution hidden
    CodeBlock.tsx              ← shiki-highlighted code
    SolutionSpoiler.tsx        ← accordion reveal
```

---

## SYNTAX HIGHLIGHTING

Use `shiki` (server-side). Create `src/lib/highlight.ts`:

```typescript
import { createHighlighter } from 'shiki';

let highlighter: Awaited<ReturnType<typeof createHighlighter>> | null = null;

export async function getHighlighter() {
  if (!highlighter) {
    highlighter = await createHighlighter({
      themes: ['github-dark', 'github-light'],
      langs: ['typescript', 'javascript', 'sql', 'bash', 'json', 'css', 'html', 'graphql', 'dockerfile'],
    });
  }
  return highlighter;
}

export async function highlight(code: string, lang: string, theme: 'github-dark' | 'github-light' = 'github-dark') {
  const h = await getHighlighter();
  return h.codeToHtml(code, { lang, theme });
}
```

Parse code blocks from markdown and pass them through `highlight()` before rendering.

---

## NEXT.JS CONFIG

```typescript
// next.config.ts
const config = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
};
```

---

## NETLIFY CONFIG

Create `netlify.toml` at project root:

```toml
[build]
  command = "npm run build"
  publish = "out"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

---

## TAILWIND & SHADCN SETUP

- Init Tailwind with `tailwind.config.ts`
- Dark mode: `class` strategy
- Install and init shadcn/ui: `npx shadcn@latest init` with `slate` base color
- Install components: `button`, `card`, `badge`, `accordion`, `progress`, `separator`, `tabs`, `input`, `select`, `sheet` (mobile nav)

---

## PACKAGE.JSON SCRIPTS

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "export": "next build && next export"
  }
}
```

---

## WHAT TO DELIVER IN THIS PROMPT

1. Complete `package.json` with all dependencies
2. `next.config.ts`, `tailwind.config.ts`, `tsconfig.json`
3. `netlify.toml`
4. All `src/` directories and file stubs (types, lib, components, app routes)
5. `content/` directory structure with empty JSON files
6. Copy existing `topics/` into `content/topics/` (preserve all existing `.md` files)
7. Working `npm run dev` — home page must render without errors
8. `LocaleContext` fully implemented
9. `Navbar` with locale switcher and theme toggle — fully functional
10. All data loader functions in `src/lib/` — fully implemented (read from files)

Do NOT generate question/task/quiz content — that is Prompt 2.
Do NOT implement full page UI — that is Prompt 3.

---

## IMPORTANT CONSTRAINTS

- Every file must compile with TypeScript strict mode
- No `any` types
- All server-only code must NOT be imported in client components
- `generateStaticParams` must be implemented for all dynamic routes
- The app must build successfully with `npm run build`
