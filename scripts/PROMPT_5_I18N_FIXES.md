# PROMPT 5 — i18n, Responsive Fixes, Quiz Content, Code Colors

> Run in the `full-stack-trainer/` directory.
> This prompt implements translations, responsive fixes, quiz from content/quiz, and inline code color fixes.

---

## TASK 1 — Translations file

Create `src/i18n/translations.ts` with all UI strings in EN and RU:

```typescript
export const translations = {
  nav: {
    theory:    { en: 'Theory',    ru: 'Теория' },
    questions: { en: 'Questions', ru: 'Вопросы' },
    quiz:      { en: 'Quiz',      ru: 'Квиз' },
    tasks:     { en: 'Tasks',     ru: 'Задачи' },
  },
  home: {
    subtitle: {
      en: 'Structured interview preparation for senior fullstack developers. Theory, questions, quizzes, and coding tasks — all in one place.',
      ru: 'Структурированная подготовка к интервью для senior fullstack разработчиков. Теория, вопросы, квизы и задачи — всё в одном месте.',
    },
    sections:       { en: 'Sections',       ru: 'Разделы' },
    topics:         { en: 'Topics',         ru: 'Темы' },
    coverageLevels: { en: 'Coverage Levels', ru: 'Уровни покрытия' },
    btnQuiz:        { en: 'Take a Quiz',    ru: 'Пройти квиз' },
    btnTheory:      { en: 'Start with Theory', ru: 'Начать с теории' },
    theoryDesc: {
      en: 'In-depth articles on each topic with code examples.',
      ru: 'Подробные статьи по каждой теме с примерами кода.',
    },
    questionsDesc: {
      en: 'Interview questions with hidden answers — Junior to Advanced.',
      ru: 'Вопросы для интервью со скрытыми ответами — от Junior до Advanced.',
    },
    quizDesc: {
      en: 'Test yourself with multiple-choice quizzes and instant feedback.',
      ru: 'Проверь себя с помощью квизов с мгновенной обратной связью.',
    },
    tasksDesc: {
      en: 'Coding challenges with starter code and hidden solutions.',
      ru: 'Задачи по программированию со стартовым кодом и скрытыми решениями.',
    },
    deepDesc: {
      en: '5 topics — comprehensive coverage with advanced questions',
      ru: '5 тем — исчерпывающее покрытие с продвинутыми вопросами',
    },
    mediumDesc: {
      en: '15 topics — solid fundamentals and common interview areas',
      ru: '15 тем — крепкие основы и типичные темы интервью',
    },
    lightDesc: {
      en: '7 topics — key concepts and essential knowledge',
      ru: '7 тем — ключевые концепции и базовые знания',
    },
  },
  footer: {
    tagline: {
      en: 'Interview preparation for senior fullstack developers',
      ru: 'Подготовка к интервью для senior fullstack разработчиков',
    },
  },
  theory: {
    title:        { en: 'Theory',        ru: 'Теория' },
    available:    { en: 'topics available', ru: 'тем доступно' },
    articles:     { en: 'articles',      ru: 'статей' },
    comingSoon:   { en: 'Coming soon',   ru: 'Скоро' },
    minRead:      { en: 'min',           ru: 'мин' },
  },
  questions: {
    title:       { en: 'Questions',          ru: 'Вопросы' },
    subtitle:    { en: 'interview questions across', ru: 'вопросов для интервью по' },
    topicsWord:  { en: 'topics',             ru: 'темам' },
    questionsWord: { en: 'questions',        ru: 'вопросов' },
    search:      { en: 'Search questions...', ru: 'Поиск вопросов...' },
    markReviewed: { en: 'Mark as reviewed',  ru: 'Отметить изученным' },
    reviewed:    { en: 'Reviewed',           ru: 'Изучено' },
    progress:    { en: 'questions in',       ru: 'вопросов по' },
    reset:       { en: 'reset',              ru: 'сбросить' },
    tags:        { en: 'Tags',               ru: 'Теги' },
    showTags:    { en: 'Show tags',          ru: 'Показать теги' },
    hideTags:    { en: 'Hide tags',          ru: 'Скрыть теги' },
    showAnswer:  { en: 'Show answer',        ru: 'Показать ответ' },
    hideAnswer:  { en: 'Hide answer',        ru: 'Скрыть ответ' },
  },
  quiz: {
    title:       { en: 'Quiz',               ru: 'Квиз' },
    subtitle:    { en: 'Test your knowledge with multiple-choice questions', ru: 'Проверь свои знания с помощью вопросов с выбором ответа' },
    startBtn:    { en: 'Start Quiz',         ru: 'Начать квиз' },
    questionOf:  { en: 'Question',           ru: 'Вопрос' },
    of:          { en: 'of',                 ru: 'из' },
    correct:     { en: 'Correct',            ru: 'Правильно' },
  },
  tasks: {
    title:       { en: 'Tasks',              ru: 'Задачи' },
    subtitle:    { en: 'Coding challenges —', ru: 'Задачи по программированию —' },
    tasksWord:   { en: 'tasks across',       ru: 'задач по' },
    topicsWord:  { en: 'topics',             ru: 'темам' },
    tasksCount:  { en: 'tasks',              ru: 'задач' },
    showSolution: { en: 'Show Solution',     ru: 'Показать решение' },
    hideSolution: { en: 'Hide Solution',     ru: 'Скрыть решение' },
    starterCode: { en: 'Starter Code',       ru: 'Стартовый код' },
    revealSolution: { en: 'Reveal solution', ru: 'Открыть решение' },
    copy:        { en: 'Copy',               ru: 'Копировать' },
    copied:      { en: 'Copied!',            ru: 'Скопировано!' },
  },
} as const;

export type TranslationKey = typeof translations;
```

Then update the `useLocale` hook (or LocaleContext) to expose a `t2()` helper that reads from this file:

```typescript
// Usage in components:
// const { t2, locale } = useLocale();
// t2('nav.theory') → 'Theory' or 'Теория'
```

Implement `t2(key: string)` as a dot-notation path resolver into the translations object that returns the correct locale string.

Apply `t2()` to EVERY hardcoded UI string across ALL components and pages listed above.
Do not leave any hardcoded EN strings in the JSX — all UI text must go through `t2()`.

---

## TASK 2 — Quiz reads from content/quiz/

The quiz currently generates questions dynamically from content/questions/.
Change it to read from `content/quiz/*.json` files instead.

These files now exist at `content/quiz/{topicId}.json` with this schema:
```typescript
interface QuizQuestion {
  id: string;
  topicId: string;
  question: { en: string; ru: string };
  options: { en: string[]; ru: string[] };  // always 4 options
  correctIndex: number;                      // 0-3
  explanation: { en: string; ru: string };
}
```

Update `src/lib/quiz.ts`:
```typescript
// Read from content/quiz/*.json
export function getQuizQuestions(topicIds?: string[], count?: number): QuizQuestion[]
export function getAvailableQuizTopics(): string[]
```

Update quiz config page to only show topics that have quiz files.
Update quiz session to use the new data source.
The quiz UI should show:
- Question text (localized)
- 4 radio options (localized)
- After selecting: highlight correct (green) / wrong (red), show explanation
- correctIndex determines which option is correct

---

## TASK 3 — Inline code color fix

Find the global CSS file (likely `src/app/globals.css`).

Replace the current inline code styles with:
```css
/* Inline code — consistent with github-dark palette */
.article-body code:not(.shiki code),
.question-answer code:not(.shiki code),
.task-description code:not(.shiki code) {
  background-color: transparent;
  color: #e6edf3;          /* github-dark foreground */
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.875em;
  padding: 0.1em 0.3em;
  border-radius: 3px;
  border: 1px solid #30363d;  /* github-dark border */
}

/* Light mode override */
.light .article-body code:not(.shiki code),
.light .question-answer code:not(.shiki code),
.light .task-description code:not(.shiki code) {
  color: #24292f;             /* github-light foreground */
  border-color: #d0d7de;      /* github-light border */
}
```

Also add the selector `.question-answer` to the QuestionCard answer container,
and `.task-description` to the task description container if not already present.

---

## TASK 4 — Responsive: center mobile cards on home page

On the home page, the section cards (Theory, Questions, Quiz, Tasks) show icon + title + description.
On mobile (< 640px), center-align everything inside each card:

```css
@media (max-width: 639px) {
  .section-card {
    text-align: center;
  }
  .section-card .icon {
    margin: 0 auto;
  }
}
```

Apply via Tailwind: add `sm:text-left text-center` to text elements and `mx-auto sm:mx-0` to icon inside the card component.

---

## TASK 5 — Tags collapsible on questions page

On the questions page (both `/questions` and `/questions/[topicId]`), the tag list takes too much vertical space.

Replace the always-visible tag list with a collapsible accordion:

```
┌──────────────────────────────────────┐
│  [▶ Show tags / Показать теги]       │  ← collapsed by default
└──────────────────────────────────────┘

When expanded:
┌──────────────────────────────────────┐
│  [▼ Hide tags / Скрыть теги]         │
│                                      │
│  [closure] [event-loop] [async] ...  │
│  [promise] [prototype] ...           │
└──────────────────────────────────────┘
```

- Use shadcn/ui `Collapsible` component
- Toggle button text uses `t2('questions.showTags')` / `t2('questions.hideTags')`
- Collapsed by default on both mobile and desktop
- Smooth height transition (CSS, no JS animation library)
- Selected tags remain active when collapsed (show count badge on toggle button: "Tags (3)")

---

## TASK 6 — Favicon

Move `favicon.ico` from project root to `src/app/favicon.ico`.
Next.js App Router automatically picks it up from `src/app/` and adds it to `<head>`.
If the file is a `.png`, rename to `icon.png` and place in `src/app/icon.png`.

---

## FINAL CHECK

After all tasks:
```bash
npm run build
```

Fix any TypeScript errors before finishing.
Report: how many components were updated with t2(), confirm quiz reads from content/quiz/, confirm build passes.
