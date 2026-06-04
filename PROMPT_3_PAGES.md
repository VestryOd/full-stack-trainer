# PROMPT 3 — Full UI Implementation

> Run this prompt AFTER Prompt 2 is complete and all content JSON files are populated.
> Run in the `full-stack-trainer/` directory.
> This prompt implements ALL page UI and interactive components.

---

## YOUR ROLE

You are a senior frontend engineer building a production-grade study tool.
Design philosophy: **clean, focused, developer-aesthetic**. Not corporate, not playful.
Think: Linear, Vercel docs, Rauno Fränberg's work. Dark mode first.

Tech: Next.js 14 App Router · shadcn/ui · Tailwind · TypeScript. Already installed from Prompt 1.

---

## DESIGN SYSTEM

Apply these design decisions consistently across ALL pages:

```css
/* Base aesthetic */
--background: #0a0a0a        /* near-black, not pure black */
--surface: #111111            /* card backgrounds */
--surface-raised: #1a1a1a    /* elevated cards */
--border: #222222             /* subtle borders */
--text-primary: #f5f5f5
--text-secondary: #888888
--text-muted: #555555
--accent: #3b82f6             /* blue-500 — single accent color */
--accent-hover: #2563eb
--success: #22c55e
--warning: #f59e0b
--error: #ef4444

/* Typography */
font-family: 'JetBrains Mono', monospace    /* headings and labels */
font-family: 'Inter', sans-serif            /* body text */
/* Load both via next/font */

/* Spacing rhythm: 4px base */
/* Border radius: 6px cards, 4px buttons, 2px badges */
/* Shadows: subtle, dark-mode appropriate */
```

**Light mode:** invert the palette tastefully — off-white (#fafafa) background, dark text. NOT a simple color flip — check contrast on every element.

---

## PAGE IMPLEMENTATIONS

### 1. Home Page (`src/app/page.tsx`)

Layout:
- Full-height hero section: title "Full-Stack Interview Trainer", subtitle "Prepare for senior engineering interviews. Theory, questions, quizzes, and coding tasks — all in one place."
- 4 feature cards in a 2×2 grid (or horizontal on desktop): Theory, Questions, Quiz, Tasks — each with icon, title, description, and CTA button
- Stats bar below: total question count, total task count, topic count — pulled from actual data at build time
- No images needed

Interactive:
- Animated count-up for stats on mount (simple CSS/JS, no library)
- Hover effects on feature cards

### 2. Theory Index (`src/app/theory/page.tsx`)

- Topic grid: 3 columns desktop, 2 tablet, 1 mobile
- Each topic card shows: topic name, level badge (Deep/Medium/Light with color coding), article count
- Filter tabs: All | Deep | Medium | Light
- Search input: filters topics by name client-side
- Click → goes to `/theory/[topicId]/`

### 3. Theory Topic Page (`src/app/theory/[topicId]/page.tsx`)

- Lists all `.md` articles for the topic
- Each article shown as a card with: title (from first `# heading` in the MD), estimated read time
- Language toggle at top: **EN | RU** — client-side switch, loads different markdown file
- Click article → `/theory/[topicId]/[slug]/`

### 4. Article Page (`src/app/theory/[topicId]/[slug]/page.tsx`)

- Renders markdown content
- Code blocks: shiki-highlighted, language label in top-right, copy-to-clipboard button
- Language toggle: **EN | RU** — switches article locale without navigation (swaps content client-side)
- Table of contents: sticky right sidebar on desktop (generated from headings), highlights current section on scroll
- Breadcrumb: Home → Theory → [Topic] → [Article]
- Previous/Next article navigation at bottom

### 5. Questions Index (`src/app/questions/page.tsx`)

Layout:
- Left sidebar (desktop) / top filter bar (mobile) with:
  - Topic multi-select checkboxes
  - Difficulty filter: All | Junior | Middle | Senior | Advanced
  - Tag filter (auto-populated from all question tags)
  - "Reset filters" link
- Main area: question list (filtered, virtualized if >100 items)
- Question count shown: "Showing 47 of 312 questions"

### 6. Questions Topic Page (`src/app/questions/[topicId]/page.tsx`)

- Same as Questions Index but pre-filtered to one topic
- Breadcrumb navigation

### 7. Question Card Component (`src/components/questions/QuestionCard.tsx`)

This is the core UX of the whole site. Get this right.

```
┌─────────────────────────────────────────────────────┐
│  [senior] [event-loop] [async]                      │
│                                                     │
│  What is the difference between microtasks and      │
│  macrotasks in the JavaScript event loop?           │
│                                  [EN] [RU]  [▼]    │
├─────────────────────────────────────────────────────┤
│  ▼ Show Answer                                      │  ← collapsed by default
│                                                     │
│  Microtasks (Promise callbacks, queueMicrotask)     │
│  are processed after the current task completes     │
│  but BEFORE the next macrotask...                   │
│                                                     │
│  ```typescript                                      │
│  console.log('1');                                  │
│  setTimeout(() => console.log('2'), 0);             │
│  Promise.resolve().then(() => console.log('3'));    │
│  // Output: 1, 3, 2                                 │
│  ```                                                │
│                                                     │
│  **Common trap:** ...                               │
└─────────────────────────────────────────────────────┘
```

- Answer text supports markdown (including code blocks with shiki highlight)
- Per-card locale switch: EN / RU toggle in top-right of card
- Smooth accordion animation on expand/collapse
- "Mark as reviewed" button — saves to localStorage, shows ✓ indicator
- Keyboard: Space/Enter to toggle when focused

### 8. Quiz Config Page (`src/app/quiz/page.tsx`)

Form to configure a quiz session:
- Topic selector: checkboxes, "Select All" toggle
- Difficulty filter: multi-select checkboxes
- Question count: slider 5–50, default 20
- "Start Quiz" button → generates session, navigates to `/quiz/[sessionId]/`
- Session stored in sessionStorage (not URL params — questions could be many)

### 9. Quiz Session Page (`src/app/quiz/[sessionId]/page.tsx`)

Active quiz UX:

```
Progress: 7 / 20          [Exit]
━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░  35%

┌─────────────────────────────────────────────┐
│  What is the output of this code?           │
│  ```js                                      │
│  console.log(typeof null);                  │
│  ```                                        │
└─────────────────────────────────────────────┘

  ○  "null"
  ○  "undefined"
  ● "object"          ← selected
  ○  "boolean"

[Check Answer]          ← before answering
[Next Question →]       ← after answering

After answering, show explanation immediately below options.
Correct: green highlight. Wrong: red on selected + green on correct.
```

- No time limit
- Shows score at end
- Explanation always shown after answering (not just on wrong)
- Locale toggle affects question AND options AND explanation

### 10. Quiz Result Page (inline in session page, shown after last question)

```
┌──────────────────────────────────────┐
│           Quiz Complete              │
│                                      │
│           14 / 20                    │
│              70%                     │
│                                      │
│  ●●●●●●●●●●●●●●○○○○○○               │
│                                      │
│  Topics: JavaScript (8/10)           │
│          React (6/10)                │
│                                      │
│  [Review Answers]  [New Quiz]        │
└──────────────────────────────────────┘
```

### 11. Tasks Browser (`src/app/tasks/page.tsx`)

- Filter sidebar: topic, difficulty (easy/medium/hard), tags
- Task cards in a list (not grid — tasks need more description space):

```
┌────────────────────────────────────────────────────┐
│  [medium] [javascript] [closures]                  │
│  Implement debounce()                              │
│                                                    │
│  Implement a debounce(fn, delay) function that...  │
│                                          [Solve →] │
└────────────────────────────────────────────────────┘
```

### 12. Task Detail Page (`src/app/tasks/[topicId]/[taskId]/page.tsx`)

```
Breadcrumb: Tasks → JavaScript → Implement debounce()

[medium]  Implement debounce()
──────────────────────────────

Description (markdown, may contain code):
  Implement a debounce(fn, delay) function...
  
  Example:
  ```typescript
  const debouncedSave = debounce(save, 300);
  ```

Starter Code:
┌──────────────────────────────────────┐
│  function debounce(fn, delay) {      │  ← shiki highlighted, copy button
│    // implement here                 │
│  }                                   │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  ▼ Show Solution                     │  ← accordion, collapsed by default
├──────────────────────────────────────┤
│  function debounce(fn, delay) {      │
│    let timer = null;                 │
│    ...                               │
│  }                                   │
│                                      │
│  **Explanation:**                    │
│  Key points:                         │
│  - Store timer ID in closure...      │
│  - cancel() clears pending timeout  │
│                                      │
│  Common mistakes:                    │
│  - Forgetting to clear previous...  │
└──────────────────────────────────────┘

Navigation: [← Previous Task]  [Next Task →]
```

- "Copy starter code" button
- "Copy solution" button (only after solution is revealed)
- "Mark as solved" → saves to localStorage, shows ✓

### 13. Progress Tracking

Implement a `src/lib/progress.ts` (client-side only):

```typescript
interface ProgressStore {
  reviewedQuestions: string[];   // question IDs
  solvedTasks: string[];         // task ID
  quizHistory: QuizHistoryEntry[];
}

interface QuizHistoryEntry {
  date: string;
  score: number;
  total: number;
  topics: string[];
}
```

Persist to localStorage key `'fst-progress'`. Expose hooks:
- `useProgress()` — returns current store + update functions
- `useQuestionReviewed(id)` — returns boolean + toggle
- `useTaskSolved(id)` — returns boolean + toggle

Show progress indicators:
- Questions page: "47 / 312 reviewed" in filter bar
- Tasks page: "12 / 48 solved" in header
- Topic pages: small progress bar on each topic card

---

## COMPONENT REQUIREMENTS

### CodeBlock (`src/components/tasks/CodeBlock.tsx`)

```tsx
interface CodeBlockProps {
  code: string;
  language: string;
  showCopy?: boolean;
  showLanguageLabel?: boolean;
  theme?: 'dark' | 'light';
}
```

- Server component (shiki runs server-side)
- Renders pre-highlighted HTML from shiki
- Copy button: client island pattern — wrap just the button in a `'use client'` component

### SolutionSpoiler (`src/components/tasks/SolutionSpoiler.tsx`)

```tsx
interface SolutionSpoilerProps {
  solution: string;          // code
  language: string;
  explanation: { en: string; ru: string };
}
```

- Initially hidden behind a blurred overlay + "Show Solution" button
- After click: smooth reveal animation (CSS height transition, no JS animation library)
- Once revealed, stays revealed for the session (but NOT saved to localStorage — only "Mark as solved" is saved)

### Navbar (`src/components/layout/Navbar.tsx`)

- Desktop: horizontal, sticky top, blurred background (`backdrop-blur`)
- Mobile: hamburger → Sheet (shadcn/ui) slide-in
- Active link indicator
- Locale switcher: `EN | RU` pill toggle
- Theme toggle: sun/moon icon

---

## RESPONSIVE BREAKPOINTS

Follow Tailwind defaults:
- `sm`: 640px
- `md`: 768px  
- `lg`: 1024px
- `xl`: 1280px

Critical responsive behaviors:
- Sidebar filters → top filter bar on mobile (collapsible)
- Theory ToC → hidden on mobile, shown as sticky drawer trigger
- Quiz options → larger tap targets on mobile
- Code blocks → horizontal scroll on mobile (no wrapping)

---

## ACCESSIBILITY

- All interactive elements: keyboard focusable, visible focus ring
- Accordion toggle: proper `aria-expanded`, `aria-controls`
- Quiz options: `role="radio"` group
- Color is never the only indicator (always text label too)
- Reduced motion: `@media (prefers-reduced-motion: reduce)` — disable animations

---

## ANIMATIONS

Minimal, purposeful:
- Page transitions: fade in (150ms opacity), no slide
- Accordion: height transition (200ms ease-out)
- Quiz answer reveal: fade in
- Progress bar: width transition (300ms)
- Hover on cards: subtle `translateY(-1px)` + border color change
- Count-up on homepage stats: 600ms, easeOut

No animation library — pure CSS + Tailwind `transition-*` classes.

---

## PERFORMANCE

- All pages must be Server Components by default
- Only interactive parts use `'use client'`
- Code highlighting: server-side only (shiki)
- Images: none needed (all icon-based)
- Fonts: `next/font` for both JetBrains Mono and Inter
- Bundle analyzer: add `@next/bundle-analyzer` to check no client-side bloat

---

## WHAT TO DELIVER

1. All page components fully implemented (no stubs)
2. All shared components fully implemented
3. Progress tracking system working
4. Mobile-responsive across all pages
5. Dark/light theme toggle working
6. Locale switching working on every page
7. `npm run build` passes with no errors or warnings
8. All `aria-*` attributes in place

---

## FINAL CHECK BEFORE FINISHING

Run:
```bash
npm run build
```

If there are TypeScript errors, fix ALL of them before finishing.
If there are missing `'use client'` directives, add them.
If `generateStaticParams` is missing for any dynamic route, add it.
