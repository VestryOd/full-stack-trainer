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

```bash
npm install
npm run dev
# → http://localhost:3000
```

## Build & Deploy

```bash
npm run build
# Outputs to /out — deploy to Netlify
```

## Content Structure

```
content/
  topics/     ← markdown theory articles (EN + RU)
  questions/  ← interview questions JSON (EN + RU answers)
  tasks/      ← coding tasks JSON (EN + RU descriptions)
  quiz/       ← multiple-choice quiz JSON (EN + RU)
```

## Adding Content

To add questions for a topic, edit `content/questions/{topicId}.json`.
Schema: see `src/types/index.ts` → `Question` interface.

## Topics Covered

1. JavaScript
2. TypeScript Advanced
3. React
4. Next.js
5. Node.js
6. Nest.js
7. PostgreSQL
8. Prisma ORM
9. GraphQL
10. CSS + HTML Advanced
11. Web Performance
12. Browser / JS Runtime
13. HTTP / REST
14. Testing
15. Security
16. SOLID + GRASP
17. OOP Patterns (GoF)
18. Algorithms & DS
19. System Design
20. Architecture Patterns
21. Git + Git Flow
22. CI/CD
23. Docker
24. Webpack / Vite
25. DDD (Basics)
26. TDD
27. Event-Driven / CQRS
