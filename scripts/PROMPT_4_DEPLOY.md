# PROMPT 4 — Deploy Configuration & Final Polish

> Run this prompt AFTER Prompt 3 is complete and `npm run build` passes.
> Run in the `full-stack-trainer/` directory.
> This prompt finalizes deployment config, adds missing polish, and prepares for Netlify.

---

## YOUR ROLE

You are a DevOps-aware senior engineer doing a pre-deploy checklist.
Be thorough. Check everything. Fix everything.

---

## TASK 1 — Netlify deployment configuration

Verify and finalize `netlify.toml`:

```toml
[build]
  command = "npm run build"
  publish = "out"
  environment = { NODE_VERSION = "20" }

[build.environment]
  NEXT_TELEMETRY_DISABLED = "1"

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"

[[headers]]
  for = "/out/static/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

Also create `.nvmrc`:
```
20
```

---

## TASK 2 — GitHub Actions CI

Create `.github/workflows/deploy.yml`:

```yaml
name: Build & Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Type check
        run: npx tsc --noEmit
      
      - name: Lint
        run: npm run lint
      
      - name: Build
        run: npm run build
      
      - name: Check output size
        run: du -sh out/
```

---

## TASK 3 — SEO & Meta tags

Add proper meta tags to `src/app/layout.tsx`:

```typescript
export const metadata: Metadata = {
  title: {
    default: 'Full-Stack Interview Trainer',
    template: '%s | FST'
  },
  description: 'Prepare for senior fullstack engineering interviews. Theory, questions, quizzes, and coding tasks across 27 topics.',
  keywords: ['interview', 'javascript', 'react', 'node.js', 'typescript', 'senior engineer', 'fullstack'],
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'Full-Stack Interview Trainer',
  },
};
```

Add per-page metadata to:
- Theory topic pages: `title: '{topicLabel} Theory | FST'`
- Questions pages: `title: '{topicLabel} Interview Questions | FST'`
- Tasks pages: `title: '{taskTitle} | FST'`

---

## TASK 4 — 404 Page

Create `src/app/not-found.tsx`:
- Clean 404 message
- Link back to home
- Same navbar as rest of site

---

## TASK 5 — Loading states

Add loading UI where needed:

- `src/app/loading.tsx` — global loading skeleton
- Quiz session page: skeleton while questions load from sessionStorage
- Questions list: skeleton cards (3–5) while filtering is computed

Use shadcn/ui `Skeleton` component. Match the shape of actual content.

---

## TASK 6 — Error boundaries

Create `src/app/error.tsx`:
```tsx
'use client';
// Shows when a route segment throws
// Must be 'use client' per Next.js requirement
// Include: error message, reset button, link to home
```

---

## TASK 7 — README

Create `README.md` at project root:

```markdown
# Full-Stack Interview Trainer

Interview preparation tool for senior fullstack engineers.
27 topics · Questions with bilingual answers · Interactive quizzes · Coding tasks with hidden solutions.

## Tech Stack

- Next.js 14 (App Router, static export)
- TypeScript
- Tailwind CSS + shadcn/ui
- Shiki (syntax highlighting)
- Deployed on Netlify

## Local Development

\`\`\`bash
npm install
npm run dev
# → http://localhost:3000
\`\`\`

## Build & Deploy

\`\`\`bash
npm run build
# Outputs to /out — deploy to Netlify
\`\`\`

## Content Structure

\`\`\`
content/
  topics/     ← markdown theory articles (EN + RU)
  questions/  ← interview questions JSON (EN + RU answers)
  tasks/      ← coding tasks JSON (EN + RU descriptions)
  quiz/       ← multiple-choice quiz JSON (EN + RU)
\`\`\`

## Adding Content

To add questions for a topic, edit `content/questions/{topicId}.json`.
Schema: see `src/types/index.ts` → `Question` interface.

## Topics Covered

[auto-generate from TOPICS constant]
```

---

## TASK 8 — Final build verification

Run the full check sequence:

```bash
# 1. Type check
npx tsc --noEmit

# 2. Lint
npm run lint

# 3. Build
npm run build

# 4. Check for large chunks
ls -la out/_next/static/chunks/ | sort -k5 -rn | head -20

# 5. Count output files
find out/ -type f | wc -l

# 6. Verify all routes generated
find out/ -name "index.html" | sort
```

Fix any errors found. Report the results:

```
TypeScript: ✓ no errors
Lint: ✓ no warnings  
Build: ✓ success
Largest chunk: XXX kb
Total pages: XX
Output size: XX MB
```

---

## TASK 9 — Performance audit checklist

Check each item manually and fix if failing:

- [ ] No `console.log` in production code (add eslint rule)
- [ ] No unused imports (`@typescript-eslint/no-unused-vars` enabled)
- [ ] All images (if any) have `alt` text
- [ ] All interactive elements have accessible labels
- [ ] Fonts load with `display: swap`
- [ ] No render-blocking scripts
- [ ] Code blocks don't break page layout on mobile (overflow-x: auto)
- [ ] localStorage access wrapped in try-catch (SSR safety)
- [ ] No `window` or `document` access in Server Components

---

## TASK 10 — Optional: Sitemap

Create `src/app/sitemap.ts`:

```typescript
import type { MetadataRoute } from 'next';
import { TOPICS } from '@/constants/topics';

export default function sitemap(): MetadataRoute.Sitemap {
  const base = 'https://your-site.netlify.app';
  
  const topicRoutes = TOPICS.flatMap(topic => [
    { url: `${base}/theory/${topic.id}/`, lastModified: new Date() },
    { url: `${base}/questions/${topic.id}/`, lastModified: new Date() },
  ]);
  
  return [
    { url: base, lastModified: new Date() },
    { url: `${base}/theory/`, lastModified: new Date() },
    { url: `${base}/questions/`, lastModified: new Date() },
    { url: `${base}/quiz/`, lastModified: new Date() },
    { url: `${base}/tasks/`, lastModified: new Date() },
    ...topicRoutes,
  ];
}
```

---

## DELIVERABLES

1. `netlify.toml` finalized
2. `.nvmrc` created
3. `.github/workflows/deploy.yml` created
4. Meta tags on all pages
5. `not-found.tsx` page
6. `loading.tsx` and `error.tsx` pages
7. `README.md` complete
8. Build passes with zero errors and zero TypeScript errors
9. Build output report printed

---

## DEPLOY INSTRUCTIONS (for human)

After this prompt completes:

1. Push to GitHub:
```bash
git init
git add .
git commit -m "feat: initial full-stack interview trainer"
git remote add origin https://github.com/YOUR_USERNAME/full-stack-trainer.git
git push -u origin main
```

2. Connect to Netlify:
   - Go to netlify.com → "Add new site" → "Import an existing project"
   - Connect GitHub → select `full-stack-trainer` repo
   - Build command: `npm run build`
   - Publish directory: `out`
   - Click Deploy

3. (Optional) Custom domain in Netlify settings.
