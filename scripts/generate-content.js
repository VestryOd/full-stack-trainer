#!/usr/bin/env node

/**
 * Full-Stack Trainer — Content Generator
 * Generates interview questions for all topics using Anthropic API
 *
 * Usage:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-content.js
 *
 * Resume after interruption:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-content.js --resume
 *
 * Single topic:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-content.js --topic javascript
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// ─── CONFIG ──────────────────────────────────────────────────────────────────

const API_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL = 'claude-haiku-4-5-20251001';
const QUESTIONS_DIR = path.join(__dirname, '..', 'content', 'questions');
const PROGRESS_FILE = path.join(__dirname, '.generation-progress.json');
const BATCH_SIZE = 5; // questions per API call
const DELAY_MS = 1500; // delay between API calls to avoid rate limits

if (!API_KEY) {
  console.error('❌  ANTHROPIC_API_KEY environment variable is not set');
  console.error('    Usage: ANTHROPIC_API_KEY=sk-ant-... node generate-content.js');
  process.exit(1);
}

// ─── TOPIC DEFINITIONS ───────────────────────────────────────────────────────

const TOPICS = [
  {
    id: 'javascript',
    label: 'JavaScript',
    target: 80,
    batches: [
      { difficulty: 'junior',   count: 15, areas: 'variables/scoping/hoisting, basic types, functions, DOM basics, ES6 syntax (arrow functions, destructuring, spread), basic async (callbacks, setTimeout)' },
      { difficulty: 'middle',   count: 20, areas: 'closures, prototype chain, this binding, Promise, async/await, array methods, Object methods, error handling, modules (ESM/CJS), regular expressions' },
      { difficulty: 'senior',   count: 25, areas: 'event loop microtasks/macrotasks, generators and async generators, Proxy and Reflect, Symbol and well-known symbols, WeakMap/WeakSet/WeakRef, memory leaks, AbortController, structured clone, tagged template literals, iterators and iterable protocol' },
      { difficulty: 'advanced', count: 20, areas: 'V8 internals and optimization, coercion edge cases, circular dependencies in ESM/CJS, temporal dead zone nuances, tail call optimization, SharedArrayBuffer and Atomics, custom thenables, promise cancellation patterns, engine-specific behaviors' },
    ],
  },
  {
    id: 'typescript',
    label: 'TypeScript',
    target: 40,
    batches: [
      { difficulty: 'junior',   count: 8,  areas: 'basic types, interfaces vs types, enums, type assertions, optional chaining, generics basics, utility types (Partial/Required/Pick/Omit/Readonly)' },
      { difficulty: 'middle',   count: 10, areas: 'generics constraints, conditional types basics, mapped types, template literal types, discriminated unions, type guards, declaration merging, module augmentation' },
      { difficulty: 'senior',   count: 12, areas: 'infer keyword, distributive conditional types, variance (covariance/contravariance), satisfies operator, const assertion, recursive types, higher-kinded types simulation, implementing utility types from scratch' },
      { difficulty: 'advanced', count: 10, areas: 'type-level programming, phantom types, branded types, builder pattern with types, exhaustiveness checking, complex infer patterns, TypeScript compiler API basics' },
    ],
  },
  {
    id: 'react',
    label: 'React',
    target: 60,
    batches: [
      { difficulty: 'junior',   count: 12, areas: 'JSX, props and state, useState/useEffect basics, event handling, lists and keys, conditional rendering, component composition, lifting state up' },
      { difficulty: 'middle',   count: 15, areas: 'useCallback/useMemo, useRef, useContext, custom hooks, controlled vs uncontrolled inputs, React.memo, error boundaries, portals, fragments' },
      { difficulty: 'senior',   count: 18, areas: 'Fiber architecture and reconciliation, concurrent features (useTransition/useDeferredValue/Suspense), stale closures in hooks, context re-render optimization, key prop reconciliation, render phases, batching in React 18' },
      { difficulty: 'advanced', count: 15, areas: 'React Server Components, streaming SSR, hydration mismatch debugging, scheduler internals, lane model, custom renderers concept, React 19 features, compiler (React Forget) concepts' },
    ],
  },
  {
    id: 'nextjs',
    label: 'Next.js',
    target: 35,
    batches: [
      { difficulty: 'junior',   count: 7,  areas: 'file-based routing, pages vs app router, getStaticProps/getServerSideProps, Image component, Link component, API routes basics' },
      { difficulty: 'middle',   count: 10, areas: 'App Router layouts, Server vs Client components, data fetching patterns, middleware, dynamic routes, generateStaticParams, metadata API' },
      { difficulty: 'senior',   count: 10, areas: 'caching layers (full route cache, data cache, router cache), streaming with Suspense, parallel and intercepting routes, server actions, ISR strategies, edge runtime' },
      { difficulty: 'advanced', count: 8,  areas: 'Next.js internals, custom webpack config, bundle optimization, module federation with Next.js, deployment strategies, multi-zone architecture' },
    ],
  },
  {
    id: 'nodejs',
    label: 'Node.js',
    target: 50,
    batches: [
      { difficulty: 'junior',   count: 10, areas: 'module system, fs/path/http modules, npm basics, package.json, basic Express, environment variables, process object' },
      { difficulty: 'middle',   count: 15, areas: 'streams and backpressure, EventEmitter, error handling patterns, middleware pattern, REST API design, authentication with JWT, database connections, clustering basics' },
      { difficulty: 'senior',   count: 15, areas: 'event loop phases (timers/IO/idle/poll/check/close), process.nextTick vs setImmediate vs Promise, Worker Threads vs cluster vs child_process, AsyncLocalStorage, memory management and GC, performance profiling' },
      { difficulty: 'advanced', count: 10, areas: 'libuv internals, native addons (N-API), V8 integration, diagnostic channels, async hooks, performance hooks, security hardening, container-aware Node.js' },
    ],
  },
  {
    id: 'nestjs',
    label: 'Nest.js',
    target: 25,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'decorators, modules, controllers, providers/services, dependency injection basics, pipes, guards basics' },
      { difficulty: 'middle',   count: 10, areas: 'dependency injection advanced (scopes, circular deps), interceptors, exception filters, custom decorators, middleware, lifecycle hooks, configuration module, TypeORM/Prisma integration' },
      { difficulty: 'senior',   count: 10, areas: 'microservices (TCP/Redis/Kafka transports), CQRS module, event sourcing patterns, dynamic modules, custom providers (useFactory/useValue/useExisting), testing with Jest in Nest context, performance optimization' },
    ],
  },
  {
    id: 'postgresql',
    label: 'PostgreSQL',
    target: 35,
    batches: [
      { difficulty: 'junior',   count: 7,  areas: 'basic SQL (SELECT/INSERT/UPDATE/DELETE), JOINs, WHERE/ORDER BY/GROUP BY, basic data types, PRIMARY KEY/FOREIGN KEY, basic indexes' },
      { difficulty: 'middle',   count: 10, areas: 'indexes (B-tree/Hash/GIN/GiST), EXPLAIN/EXPLAIN ANALYZE, transactions and isolation levels, window functions, CTEs, JSONB operations, constraints' },
      { difficulty: 'senior',   count: 10, areas: 'query planner internals, vacuum and autovacuum, MVCC, partitioning, connection pooling (PgBouncer), replication basics, performance tuning, pg_stat_* views' },
      { difficulty: 'advanced', count: 8,  areas: 'custom types and domains, stored procedures vs functions, triggers, row-level security, logical replication, pg_logical, extensions (pg_vector, PostGIS concepts), write-ahead log' },
    ],
  },
  {
    id: 'prisma',
    label: 'Prisma ORM',
    target: 20,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'schema definition, basic CRUD operations, relations (one-to-one/one-to-many/many-to-many), migrations, Prisma Client setup' },
      { difficulty: 'middle',   count: 8,  areas: 'nested writes, transactions, filtering and pagination, select and include, raw queries, schema validation, middleware' },
      { difficulty: 'senior',   count: 7,  areas: 'N+1 problem in Prisma, performance optimization, connection management, custom generators, multi-schema support, Prisma vs TypeORM trade-offs' },
    ],
  },
  {
    id: 'graphql',
    label: 'GraphQL',
    target: 25,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'queries and mutations, schema definition language, types (scalar/object/enum/input), resolvers basics, GraphQL vs REST' },
      { difficulty: 'middle',   count: 10, areas: 'fragments, variables, directives, subscriptions, Apollo Client (useQuery/useMutation), InMemoryCache, error handling (partial errors), introspection' },
      { difficulty: 'senior',   count: 10, areas: 'N+1 problem and DataLoader, resolver chain and context object, schema stitching vs federation, persisted queries, performance optimization, security (depth limiting, query complexity), file uploads' },
    ],
  },
  {
    id: 'css-html',
    label: 'CSS + HTML Advanced',
    target: 35,
    batches: [
      { difficulty: 'junior',   count: 7,  areas: 'box model, flexbox, basic grid, selectors specificity, positioning, basic animations, semantic HTML, forms' },
      { difficulty: 'middle',   count: 10, areas: 'CSS Grid advanced, custom properties (CSS vars), pseudo-elements/classes, BEM methodology, responsive design, media queries, CSS transforms, accessibility (ARIA)' },
      { difficulty: 'senior',   count: 10, areas: 'stacking context and z-index, contain property, CSS layers (@layer), logical properties, container queries, scroll-driven animations, paint worklets concept, critical CSS' },
      { difficulty: 'advanced', count: 8,  areas: 'browser rendering pipeline (style/layout/paint/composite), GPU compositing layers, will-change, CSS Houdini, shadow DOM styling, CSS-in-JS trade-offs, rendering performance' },
    ],
  },
  {
    id: 'web-performance',
    label: 'Web Performance',
    target: 25,
    batches: [
      { difficulty: 'middle',   count: 10, areas: 'Core Web Vitals (LCP/CLS/INP/FID), resource hints (preload/prefetch/preconnect), lazy loading, image optimization, code splitting, tree shaking' },
      { difficulty: 'senior',   count: 10, areas: 'Chrome DevTools Performance panel, Long Tasks, JavaScript execution budget, render-blocking resources, font loading strategies, service workers and caching, bundle analysis' },
      { difficulty: 'advanced', count: 5,  areas: 'browser rendering pipeline optimization, memory profiling, frame budget (16ms), WebAssembly for performance-critical code, HTTP/2 and HTTP/3 impact' },
    ],
  },
  {
    id: 'browser-runtime',
    label: 'Browser / JS Runtime',
    target: 35,
    batches: [
      { difficulty: 'junior',   count: 7,  areas: 'DOM tree, event bubbling/capturing, localStorage/sessionStorage/cookies, fetch API basics, CORS basics' },
      { difficulty: 'middle',   count: 10, areas: 'event delegation, MutationObserver/IntersectionObserver/ResizeObserver, Web Workers, requestAnimationFrame, History API, Web Storage security' },
      { difficulty: 'senior',   count: 10, areas: 'browser rendering pipeline (parse/style/layout/paint/composite), critical rendering path, reflow vs repaint, V8 JIT compilation, hidden classes and inline caches, garbage collection in browser' },
      { difficulty: 'advanced', count: 8,  areas: 'SharedArrayBuffer and Atomics, WebAssembly integration, Service Worker lifecycle, IndexedDB patterns, WebRTC concepts, WebGPU concepts, browser security model (same-origin, CSP)' },
    ],
  },
  {
    id: 'http-rest',
    label: 'HTTP / REST',
    target: 25,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'HTTP methods, status codes, headers, REST principles, JSON API basics, authentication basics' },
      { difficulty: 'middle',   count: 10, areas: 'REST best practices, versioning strategies, HATEOAS, caching (ETag/Cache-Control/Last-Modified), CORS in depth, rate limiting, pagination patterns' },
      { difficulty: 'senior',   count: 10, areas: 'HTTP/2 multiplexing, HTTP/3 and QUIC, TLS handshake, WebSockets vs SSE vs Long Polling, API gateway patterns, idempotency, distributed tracing (OpenTelemetry basics)' },
    ],
  },
  {
    id: 'testing',
    label: 'Testing',
    target: 25,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'unit vs integration vs e2e, Jest basics, describe/it/expect, mocking basics, React Testing Library basics' },
      { difficulty: 'middle',   count: 10, areas: 'mock vs stub vs spy, testing async code, testing hooks (renderHook), snapshot testing trade-offs, code coverage metrics, test doubles patterns' },
      { difficulty: 'senior',   count: 10, areas: 'testing pyramid vs testing trophy, contract testing, property-based testing, testing microservices, MSW (Mock Service Worker), Playwright for e2e, performance testing, TDD in practice' },
    ],
  },
  {
    id: 'security',
    label: 'Security',
    target: 25,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'XSS types (reflected/stored/DOM), CSRF, SQL injection, HTTPS basics, password hashing' },
      { difficulty: 'middle',   count: 10, areas: 'CSP headers, JWT structure and validation, OAuth 2.0 flows, CORS security, cookie security flags (HttpOnly/Secure/SameSite), input validation' },
      { difficulty: 'senior',   count: 10, areas: 'OWASP Top 10 for web apps, JWT pitfalls (algorithm confusion, none algorithm), refresh token rotation, security headers audit, dependency vulnerabilities, secrets management, rate limiting strategies' },
    ],
  },
  {
    id: 'solid-grasp',
    label: 'SOLID + GRASP',
    target: 25,
    batches: [
      { difficulty: 'middle',   count: 10, areas: 'SRP/OCP/LSP/ISP/DIP — each principle with JS/TS code example, common violations and how to fix them' },
      { difficulty: 'senior',   count: 10, areas: 'GRASP patterns (Information Expert, Creator, Controller, Low Coupling, High Cohesion), applying SOLID to React components, SOLID violations in real codebases' },
      { difficulty: 'advanced', count: 5,  areas: 'trade-offs of strict SOLID adherence, SOLID in functional programming context, over-engineering risks, pragmatic application' },
    ],
  },
  {
    id: 'oop-patterns',
    label: 'OOP Patterns (GoF)',
    target: 30,
    batches: [
      { difficulty: 'middle',   count: 12, areas: 'Creational: Singleton, Factory, Abstract Factory, Builder, Prototype — each with JS/TS example and when to use' },
      { difficulty: 'senior',   count: 12, areas: 'Structural: Adapter, Bridge, Composite, Decorator, Facade, Flyweight, Proxy — each with JS/TS example. Behavioral: Observer, Strategy, Command, Iterator, Template Method' },
      { difficulty: 'advanced', count: 6,  areas: 'pattern combinations, anti-patterns, patterns in React (HOC=Decorator, Render Props, Compound Components), patterns in Node.js (Middleware=Chain of Responsibility)' },
    ],
  },
  {
    id: 'algorithms',
    label: 'Algorithms & DS',
    target: 40,
    batches: [
      { difficulty: 'junior',   count: 8,  areas: 'Big O notation, arrays, strings, basic sorting (bubble/selection/insertion), linear search, binary search' },
      { difficulty: 'middle',   count: 12, areas: 'hash maps, sets, stack, queue, linked list, tree traversal (BFS/DFS), merge sort, quick sort, two pointers, sliding window' },
      { difficulty: 'senior',   count: 12, areas: 'dynamic programming (memoization/tabulation), graphs (Dijkstra/BFS/DFS), heaps and priority queues, trie, union-find, backtracking' },
      { difficulty: 'advanced', count: 8,  areas: 'advanced DP patterns, segment trees, balanced BST concepts, NP-completeness basics, amortized analysis, cache-oblivious algorithms' },
    ],
  },
  {
    id: 'system-design',
    label: 'System Design (Frontend-aware)',
    target: 25,
    batches: [
      { difficulty: 'middle',   count: 8,  areas: 'API design between frontend and backend, BFF (Backend for Frontend) pattern, caching strategies (CDN/browser/API), pagination strategies' },
      { difficulty: 'senior',   count: 10, areas: 'micro-frontend architecture trade-offs, Module Federation design decisions, design system at scale, real-time features (WebSockets vs SSE vs polling), offline-first design' },
      { difficulty: 'advanced', count: 7,  areas: 'distributed frontend state, A/B testing infrastructure, feature flags architecture, observability (logging/metrics/tracing from frontend), multi-region deployment' },
    ],
  },
  {
    id: 'architecture',
    label: 'Architecture Patterns',
    target: 25,
    batches: [
      { difficulty: 'middle',   count: 8,  areas: 'Layered architecture, MVC/MVP/MVVM, repository pattern, service layer pattern' },
      { difficulty: 'senior',   count: 10, areas: 'Clean Architecture, Hexagonal (Ports and Adapters), Onion Architecture, Event-Driven Architecture, CQRS basics, Saga pattern' },
      { difficulty: 'advanced', count: 7,  areas: 'architecture trade-offs, when to use which architecture, strangler fig pattern for migration, architecture decision records (ADR), evolutionary architecture' },
    ],
  },
  {
    id: 'git',
    label: 'Git + Git Flow',
    target: 20,
    batches: [
      { difficulty: 'junior',   count: 6,  areas: 'basic commands (add/commit/push/pull/clone), branching, merging, .gitignore, git log' },
      { difficulty: 'middle',   count: 8,  areas: 'rebase vs merge trade-offs, cherry-pick, stash, interactive rebase, resolving conflicts, git hooks, Git Flow vs trunk-based development' },
      { difficulty: 'senior',   count: 6,  areas: 'git internals (objects: blob/tree/commit/tag), reflog, bisect, submodules, monorepo strategies, signed commits' },
    ],
  },
  {
    id: 'ci-cd',
    label: 'CI/CD',
    target: 20,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'CI/CD concepts, GitHub Actions basics (workflow/job/step), environment variables in CI, basic pipeline stages' },
      { difficulty: 'middle',   count: 8,  areas: 'GitHub Actions advanced (matrix, reusable workflows, artifacts, caching), deployment strategies (blue-green, canary, rolling), secrets management' },
      { difficulty: 'senior',   count: 7,  areas: 'pipeline optimization, deployment to Kubernetes basics, GitOps concepts, feature flags in deployment, rollback strategies, monitoring after deploy' },
    ],
  },
  {
    id: 'docker',
    label: 'Docker',
    target: 20,
    batches: [
      { difficulty: 'junior',   count: 5,  areas: 'container vs VM, basic commands (run/build/ps/logs/exec), Dockerfile basics, image layers, Docker Hub' },
      { difficulty: 'middle',   count: 8,  areas: 'multi-stage builds, docker-compose, networking (bridge/host/overlay), volumes, environment variables, health checks' },
      { difficulty: 'senior',   count: 7,  areas: 'image optimization (size reduction), security scanning, Docker in CI/CD, container orchestration concepts, Node.js in Docker (non-root user, signal handling), .dockerignore' },
    ],
  },
  {
    id: 'bundlers',
    label: 'Webpack / Vite',
    target: 20,
    batches: [
      { difficulty: 'junior',   count: 4,  areas: 'what bundlers do, entry/output/loaders/plugins concepts, development vs production builds' },
      { difficulty: 'middle',   count: 8,  areas: 'code splitting (dynamic import/SplitChunksPlugin), tree shaking requirements, source maps, HMR (Hot Module Replacement), Vite vs Webpack trade-offs' },
      { difficulty: 'senior',   count: 8,  areas: 'webpack internals (dependency graph, compilation lifecycle), custom loaders/plugins, Module Federation, bundle analysis, Vite internals (esbuild/rollup), build performance optimization' },
    ],
  },
  {
    id: 'ddd',
    label: 'DDD Basics',
    target: 15,
    batches: [
      { difficulty: 'middle',   count: 6,  areas: 'Bounded Context, Ubiquitous Language, Entity vs Value Object, Aggregate, Repository pattern, Domain Events' },
      { difficulty: 'senior',   count: 6,  areas: 'Context Mapping patterns, Anti-Corruption Layer, DDD in Node.js/TypeScript, domain model vs anemic model' },
      { difficulty: 'advanced', count: 3,  areas: 'DDD trade-offs, when NOT to use DDD, DDD with Event Sourcing' },
    ],
  },
  {
    id: 'tdd',
    label: 'TDD',
    target: 15,
    batches: [
      { difficulty: 'junior',   count: 3,  areas: 'red-green-refactor cycle, what makes a good unit test, test naming conventions' },
      { difficulty: 'middle',   count: 6,  areas: 'TDD benefits and costs, test doubles in TDD, outside-in vs inside-out TDD, applying TDD to React components' },
      { difficulty: 'senior',   count: 6,  areas: 'TDD in legacy codebases, acceptance TDD (ATDD), TDD with async code, when TDD slows you down (pragmatic view), mutation testing' },
    ],
  },
  {
    id: 'event-driven',
    label: 'Event-Driven / CQRS',
    target: 15,
    batches: [
      { difficulty: 'middle',   count: 5,  areas: 'event-driven architecture basics, message queues (concept), pub/sub pattern, event vs command vs query' },
      { difficulty: 'senior',   count: 6,  areas: 'CQRS pattern (Command Query Responsibility Segregation), event sourcing basics, eventual consistency, saga pattern for distributed transactions' },
      { difficulty: 'advanced', count: 4,  areas: 'event storming, outbox pattern, idempotency in event handling, event schema evolution' },
    ],
  },
];

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function callAnthropicAPI(prompt) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      model: MODEL,
      max_tokens: 8000,
      messages: [{ role: 'user', content: prompt }],
    });

    const options = {
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(body),
      },
    };

    const req = https.request(options, res => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(new Error(`API error: ${parsed.error.message}`));
          } else {
            resolve(parsed.content[0].text);
          }
        } catch (e) {
          reject(new Error(`Failed to parse response: ${data.slice(0, 200)}`));
        }
      });
    });

    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function loadProgress() {
  if (fs.existsSync(PROGRESS_FILE)) {
    return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));
  }
  return {};
}

function saveProgress(progress) {
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));
}

function loadQuestions(topicId) {
  const file = path.join(QUESTIONS_DIR, `${topicId}.json`);
  if (!fs.existsSync(file)) return [];
  try {
    const content = fs.readFileSync(file, 'utf8').trim();
    if (!content || content === '[]') return [];
    return JSON.parse(content);
  } catch {
    return [];
  }
}

function saveQuestions(topicId, questions) {
  const file = path.join(QUESTIONS_DIR, `${topicId}.json`);
  fs.writeFileSync(file, JSON.stringify(questions, null, 2));
}

function extractJSON(text) {
  // Try to find a JSON array in the response
  const match = text.match(/\[\s*\{[\s\S]*\}\s*\]/);
  if (match) {
    return JSON.parse(match[0]);
  }
  // Try parsing the whole text
  return JSON.parse(text.trim());
}

// ─── PROMPT BUILDER ──────────────────────────────────────────────────────────

function buildPrompt(topic, batch, startIndex, chunkSize) {
  return `Generate exactly ${chunkSize} interview questions for a Senior Fullstack Engineer interview.

Topic: ${topic.label}
Difficulty: ${batch.difficulty}
Areas to cover: ${batch.areas}

IDs must start from: ${topic.id}-q-${startIndex + 1}

Return ONLY a valid JSON array. No explanation, no markdown, no backticks. Just the raw JSON array.

Schema for each object:
{
  "id": "${topic.id}-q-${startIndex + 1}",
  "topicId": "${topic.id}",
  "difficulty": "${batch.difficulty}",
  "question": {
    "en": "Clear, specific question in English",
    "ru": "Тот же вопрос на русском языке"
  },
  "answer": {
    "en": "### Brief heading\\n\\nExplanation (2-3 sentences max).\\n\\n\`\`\`typescript\\n// Code example (max 10 lines)\\n\`\`\`\\n\\n**Common interview trap:** One sentence.",
    "ru": "### Заголовок\\n\\nОбъяснение (2-3 предложения).\\n\\n\`\`\`typescript\\n// Тот же код\\n\`\`\`\\n\\n**Типичная ошибка:** Одно предложение."
  },
  "tags": ["specific-tag-1", "specific-tag-2"]
}

Rules:
- Keep answers SHORT: 2-3 sentences + max 10 lines of code. No lengthy introductions.
- Every answer MUST have a code example in a fenced typescript block
- ${batch.difficulty === 'senior' || batch.difficulty === 'advanced' ? 'Every answer MUST include a "Common interview trap" line' : 'Include a practical short example'}
- Both en and ru fields must be complete — no placeholders
- Tags must be specific (e.g. "closures", "event-loop", not "javascript", "advanced")
- Questions must be distinct — no duplicates

Generate exactly ${chunkSize} questions now:`;
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────

async function generateBatch(topic, batch, startIndex, progress) {
  const totalNeeded = batch.count;
  const chunks = Math.ceil(totalNeeded / BATCH_SIZE);

  for (let i = 0; i < chunks; i++) {
    const chunkKey = `${topic.id}:${batch.difficulty}:chunk${i}`;

    if (progress[chunkKey] === 'done') {
      console.log(`  ⏭  Skipping ${chunkKey} (already done)`);
      startIndex += BATCH_SIZE;
      continue;
    }

    const chunkSize = Math.min(BATCH_SIZE, totalNeeded - i * BATCH_SIZE);
    console.log(`  ⚙  Generating ${chunkSize} ${batch.difficulty} questions for ${topic.label} (chunk ${i + 1}/${chunks})...`);

    const prompt = buildPrompt(topic, batch, startIndex, chunkSize);

    let attempts = 0;
    const maxAttempts = 3;
    let success = false;

    while (attempts < maxAttempts) {
      attempts++;
      try {
        const response = await callAnthropicAPI(prompt);
        const newQuestions = extractJSON(response);

        if (!Array.isArray(newQuestions) || newQuestions.length === 0) {
          throw new Error('Response is not a valid array');
        }

        const first = newQuestions[0];
        if (!first.id || !first.question?.en || !first.answer?.en) {
          throw new Error('Questions missing required fields');
        }

        const existing = loadQuestions(topic.id);
        const merged = [...existing, ...newQuestions];
        saveQuestions(topic.id, merged);

        progress[chunkKey] = 'done';
        saveProgress(progress);

        console.log(`  ✓  Added ${newQuestions.length} questions → ${topic.id}.json now has ${merged.length}`);
        startIndex += newQuestions.length;
        success = true;
        break;

      } catch (err) {
        console.error(`  ✗  Attempt ${attempts}/${maxAttempts} failed: ${err.message}`);
        if (attempts < maxAttempts) {
          console.log(`     Retrying in 3s...`);
          await sleep(3000);
        }
      }
    }

    if (!success) {
      console.error(`  ✗  Failed chunk ${chunkKey} after ${maxAttempts} attempts. Skipping.`);
    }

    await sleep(DELAY_MS);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const resumeMode = args.includes('--resume');
  const singleTopic = args.find(a => a.startsWith('--topic='))?.split('=')[1];

  console.log('🚀 Full-Stack Trainer — Content Generator');
  console.log(`   Model: ${MODEL}`);
  console.log(`   Mode: ${resumeMode ? 'resume' : 'fresh start'}${singleTopic ? ` (topic: ${singleTopic})` : ''}`);
  console.log('');

  const progress = resumeMode ? loadProgress() : {};
  if (!resumeMode) saveProgress({});

  const topicsToProcess = singleTopic
    ? TOPICS.filter(t => t.id === singleTopic)
    : TOPICS;

  if (singleTopic && topicsToProcess.length === 0) {
    console.error(`❌  Topic "${singleTopic}" not found`);
    process.exit(1);
  }

  let totalGenerated = 0;
  let totalTarget = topicsToProcess.reduce((sum, t) => sum + t.target, 0);

  for (const topic of topicsToProcess) {
    const existing = loadQuestions(topic.id);
    console.log(`\n📚 ${topic.label} (${existing.length}/${topic.target} existing)`);

    let currentIndex = existing.length;

    for (const batch of topic.batches) {
      await generateBatch(topic, batch, currentIndex, progress);
      currentIndex += batch.count;
    }

    const final = loadQuestions(topic.id);
    totalGenerated += final.length;
    console.log(`  📊 ${topic.label} complete: ${final.length} questions`);
  }

  console.log('\n' + '═'.repeat(50));
  console.log(`✅  Generation complete!`);
  console.log(`   Total questions: ${totalGenerated} / ${totalTarget} target`);
  console.log('');

  // Final validation
  console.log('🔍 Validating all files...');
  let hasErrors = false;
  for (const topic of TOPICS) {
    const questions = loadQuestions(topic.id);
    const file = path.join(QUESTIONS_DIR, `${topic.id}.json`);
    if (!fs.existsSync(file)) {
      console.log(`  ⚠  Missing: ${topic.id}.json`);
      hasErrors = true;
      continue;
    }
    const issues = questions.filter(q => !q.id || !q.question?.en || !q.answer?.en);
    if (issues.length > 0) {
      console.log(`  ⚠  ${topic.id}.json: ${issues.length} questions with missing fields`);
      hasErrors = true;
    } else {
      console.log(`  ✓  ${topic.id}.json: ${questions.length} questions`);
    }
  }

  if (!hasErrors) {
    console.log('\n✅  All files valid!');
  } else {
    console.log('\n⚠  Some files have issues. Run with --resume to retry failed batches.');
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
