# PROMPT 2 — Content Generation

> Run this prompt AFTER Prompt 1 is complete and `npm run dev` works.
> Run in the `full-stack-trainer/` directory.
> This prompt generates ALL content: questions, tasks, quiz questions, EN translations of theory articles.

---

## YOUR ROLE

You are a senior technical interviewer with 10+ years of experience hiring fullstack engineers at product companies and consultancies in Europe. You know exactly what gets asked at senior level, what distinguishes a strong answer from a mediocre one, and how to write tasks that reveal thinking, not just syntax recall.

Generate content that is accurate, technically precise, and genuinely useful for interview preparation at Senior level.

---

## CRITICAL QUALITY RULES

1. **No hallucinations** — every fact, API, method, behavior must be correct. If uncertain, omit.
2. **Senior-level depth** — don't explain what a promise is. Do explain microtask queue ordering edge cases.
3. **Code blocks must work** — all code examples must be syntactically correct and runnable.
4. **Answers must be complete** — a question without a thorough answer is useless. Every answer: concept explanation + why it matters + code example where applicable + common interview follow-up trap.
5. **Bilingual** — every `question`, `answer`, `title`, `description`, `explanation` field has both `en` and `ru` keys.
6. **IDs** — format: `{topicId}-q-{number}` for questions, `{topicId}-t-{number}` for tasks, `{topicId}-quiz-{number}` for quiz.

---

## TASK A — Verify and fix existing Russian theory articles

Read all existing markdown files in `content/topics/*/ru/`.

For each file:
1. Check for factual errors, outdated information, or misleading statements
2. Fix any errors **in place** — rewrite incorrect sections
3. Add a comment at the top of each file: `<!-- verified: YYYY-MM-DD, corrections: N -->` where N is number of corrections made (0 if none)
4. Do NOT change the structure or headings unless they are wrong

Common issues to check for in ChatGPT-generated content:
- Incorrect API signatures
- Outdated behavior (e.g., React hooks rules stated incorrectly)
- Missing nuance on async behavior
- Wrong complexity claims for algorithms
- Oversimplified explanations of PostgreSQL query planner

---

## TASK B — Generate English translations of all theory articles

For every `.md` file in `content/topics/*/ru/`:
- Create the equivalent file in `content/topics/*/en/` with the same filename
- Translate faithfully — do not add or remove content
- Code blocks stay as-is (language-agnostic)
- Technical terms stay in English (they already are)
- Translation tone: professional, precise, no fluff

---

## TASK C — Generate Questions JSON files

Write to `content/questions/{topicId}.json`. Each file is an array of `Question` objects.

### Minimum question counts per topic:

| Topic | Min questions | Difficulties |
|---|---|---|
| javascript | 40 | junior×8, middle×10, senior×12, advanced×10 |
| typescript | 25 | junior×5, middle×8, senior×7, advanced×5 |
| react | 35 | junior×7, middle×10, senior×10, advanced×8 |
| nextjs | 20 | junior×4, middle×6, senior×6, advanced×4 |
| nodejs | 25 | junior×5, middle×8, senior×7, advanced×5 |
| nestjs | 15 | junior×3, middle×5, senior×5, advanced×2 |
| postgresql | 20 | junior×4, middle×6, senior×6, advanced×4 |
| prisma | 12 | junior×3, middle×4, senior×4, advanced×1 |
| graphql | 15 | junior×3, middle×5, senior×5, advanced×2 |
| css-html | 20 | junior×5, middle×6, senior×6, advanced×3 |
| web-performance | 15 | junior×3, middle×5, senior×5, advanced×2 |
| browser-runtime | 20 | junior×4, middle×6, senior×6, advanced×4 |
| http-rest | 15 | junior×3, middle×5, senior×5, advanced×2 |
| testing | 15 | junior×3, middle×5, senior×5, advanced×2 |
| security | 12 | junior×2, middle×4, senior×4, advanced×2 |
| solid-grasp | 12 | middle×4, senior×5, advanced×3 |
| oop-patterns | 15 | middle×5, senior×6, advanced×4 |
| algorithms | 20 | junior×4, middle×6, senior×6, advanced×4 |
| system-design | 12 | middle×4, senior×5, advanced×3 |
| architecture | 12 | middle×4, senior×5, advanced×3 |
| git | 10 | junior×3, middle×4, senior×3 |
| ci-cd | 8 | junior×2, middle×3, senior×3 |
| docker | 8 | junior×2, middle×3, senior×3 |
| bundlers | 10 | junior×2, middle×4, senior×4 |
| ddd | 8 | middle×3, senior×4, advanced×1 |
| tdd | 8 | junior×2, middle×3, senior×3 |
| event-driven | 8 | middle×3, senior×3, advanced×2 |

### Question JSON schema:

```json
[
  {
    "id": "javascript-q-1",
    "topicId": "javascript",
    "difficulty": "senior",
    "question": {
      "en": "Explain the difference between microtasks and macrotasks in the JavaScript event loop. What are the practical implications for async code ordering?",
      "ru": "Объясните разницу между микрозадачами и макрозадачами в event loop JavaScript. Каковы практические последствия для порядка выполнения асинхронного кода?"
    },
    "answer": {
      "en": "### Microtasks vs Macrotasks\n\nThe event loop processes tasks in a specific priority order...\n\n```typescript\nconsole.log('1');\nsetTimeout(() => console.log('2'), 0);\nPromise.resolve().then(() => console.log('3'));\nconsole.log('4');\n// Output: 1, 4, 3, 2\n```\n\n**Why it matters:** ...\n\n**Common interview trap:** ...",
      "ru": "..."
    },
    "tags": ["event-loop", "async", "promises", "runtime"]
  }
]
```

### High-value question areas to cover (must include these, plus more):

**JavaScript:**
- Event loop: microtask queue, macrotask queue, exact execution order
- Closures: practical traps (loop + var, stale closure in hooks)
- Prototype chain: `Object.create`, `__proto__`, `prototype`, `instanceof` internals
- `this` binding: all 4 rules + arrow functions + `.call/.apply/.bind`
- Memory leaks: causes, detection, WeakMap/WeakRef
- Generators and iterators: lazy evaluation, `yield*`, async generators
- Proxy and Reflect: use cases, traps
- Symbol: well-known symbols, iterator protocol
- WeakMap/WeakSet vs Map/Set: when to use which
- Temporal dead zone: `let`/`const` vs `var` hoisting
- Coercion: `==` vs `===`, type coercion rules, `+` operator edge cases
- Tagged template literals
- Structured clone vs JSON.stringify limitations
- `AbortController` and cancellable fetch
- Module system: ESM vs CJS, circular dependencies, tree shaking implications

**React:**
- Reconciliation algorithm: Fiber architecture, priorities, lanes
- `useEffect` dependency array: stale closures, exhaustive deps rule
- `useMemo`/`useCallback`: when they help vs when they're premature optimization
- `useRef` beyond DOM: storing previous values, avoiding stale closures
- Context re-render optimization: splitting contexts, `memo` + context
- Error boundaries: what they catch, what they don't
- Concurrent features: `useTransition`, `useDeferredValue`, Suspense
- `key` prop: reconciliation role, anti-patterns (index as key)
- Custom hooks: rules of hooks under the hood, why order matters
- Portals: use cases, event bubbling behavior
- Controlled vs uncontrolled: when to use which
- `React.memo` pitfalls: reference equality, object/function props

**Node.js:**
- Event loop phases: timers, I/O callbacks, idle, poll, check, close — exact order
- `process.nextTick` vs `setImmediate` vs `Promise.resolve()`
- Streams: backpressure, `pipe`, `pipeline`, Transform streams
- Cluster vs Worker Threads vs child_process: when to use which
- `AsyncLocalStorage`: what problem it solves, use in request context
- Memory: heap, buffer, GC triggers, `--max-old-space-size`
- CommonJS vs ESM in Node: `require` cache, circular dep behavior
- Error handling: uncaughtException vs unhandledRejection, domain (legacy)

**TypeScript:**
- Conditional types: `infer`, distributive conditional types
- Mapped types: `Partial`, `Required`, `Pick`, `Omit` — implement from scratch
- Template literal types
- `satisfies` operator vs `as` vs type annotation
- Variance: covariance, contravariance in function params
- Discriminated unions: exhaustiveness checking with `never`
- Declaration merging
- `const` assertion and `as const`
- Module augmentation

---

## TASK D — Generate Tasks JSON files

Write to `content/tasks/{topicId}.json`. Each file is an array of `Task` objects.

Generate tasks for these topics: `javascript`, `typescript`, `react`, `nodejs`, `algorithms`, `css-html`, `testing`, `graphql`

### Minimum task counts:

| Topic | Easy | Medium | Hard |
|---|---|---|---|
| javascript | 5 | 8 | 5 |
| typescript | 3 | 5 | 3 |
| react | 3 | 5 | 3 |
| nodejs | 2 | 4 | 2 |
| algorithms | 5 | 8 | 5 |
| css-html | 3 | 4 | 2 |
| testing | 2 | 4 | 2 |
| graphql | 2 | 3 | 2 |

### Task JSON schema:

```json
[
  {
    "id": "javascript-t-1",
    "topicId": "javascript",
    "difficulty": "medium",
    "title": {
      "en": "Implement a debounce function",
      "ru": "Реализуй функцию debounce"
    },
    "description": {
      "en": "Implement a `debounce(fn, delay)` function that delays calling `fn` until `delay` ms have passed since the last call. Must support cancellation via `.cancel()` method on the returned function.\n\n**Example:**\n```typescript\nconst debouncedSave = debounce(save, 300);\ndebouncedSave(); // not called\ndebouncedSave(); // not called\n// 300ms later → save() is called once\n\ndebouncedSave.cancel(); // cancels pending call\n```",
      "ru": "..."
    },
    "starterCode": "function debounce<T extends (...args: unknown[]) => unknown>(\n  fn: T,\n  delay: number\n): T & { cancel: () => void } {\n  // implement here\n}",
    "solution": "function debounce<T extends (...args: unknown[]) => unknown>(\n  fn: T,\n  delay: number\n): T & { cancel: () => void } {\n  let timer: ReturnType<typeof setTimeout> | null = null;\n\n  const debounced = ((...args: Parameters<T>) => {\n    if (timer) clearTimeout(timer);\n    timer = setTimeout(() => {\n      fn(...args);\n      timer = null;\n    }, delay);\n  }) as T & { cancel: () => void };\n\n  debounced.cancel = () => {\n    if (timer) {\n      clearTimeout(timer);\n      timer = null;\n    }\n  };\n\n  return debounced;\n}",
    "solutionExplanation": {
      "en": "**Key points:**\n- Store timer ID in closure...\n- `cancel()` clears pending timeout...\n- Generic typing ensures type safety...\n\n**Common mistakes:**\n- Forgetting to clear previous timer before setting new one\n- Not handling the `this` context (matters for class methods)\n\n**Follow-up questions:**\n- How would you add a `leading` option (call immediately on first invocation)?\n- What's the difference between debounce and throttle?",
      "ru": "..."
    },
    "tags": ["closures", "timers", "higher-order-functions"]
  }
]
```

### Required tasks to include (these specifically):

**JavaScript:**
- Implement `debounce(fn, delay)` with `.cancel()`
- Implement `throttle(fn, interval)`
- Implement `deepClone(obj)` without `structuredClone` or JSON
- Implement `EventEmitter` class (on, off, emit, once)
- Implement `Promise.all` from scratch
- Implement `curry(fn)` — variadic currying
- Implement `pipe(...fns)` and `compose(...fns)`
- Flatten nested array to arbitrary depth without `Array.flat`
- Implement memoization with WeakMap (for object args) + Map (for primitive args)
- LRU Cache implementation

**TypeScript:**
- Implement `DeepReadonly<T>` utility type
- Implement `DeepPartial<T>` utility type
- Implement `Awaited<T>` from scratch (without built-in)
- Type-safe event emitter with generic event map
- Implement `Pick` and `Omit` from scratch using mapped types

**Algorithms:**
- Two Sum (hash map approach)
- Valid Parentheses (stack)
- Reverse Linked List
- Binary Search
- Maximum Subarray (Kadane's algorithm)
- Group Anagrams
- Merge Intervals
- First Missing Positive
- LRU Cache
- Serialize/Deserialize Binary Tree

**React:**
- Implement `useDebounce(value, delay)` hook
- Implement `usePrevious(value)` hook
- Implement `useLocalStorage(key, initialValue)` hook
- Implement virtualized list (render only visible items)
- Build a form with validation without any form library

---

## TASK E — Generate Quiz JSON files

Write to `content/quiz/{topicId}.json`. Each file is an array of `QuizQuestion` objects.

Generate quiz questions for: `javascript`, `typescript`, `react`, `nextjs`, `nodejs`, `nestjs`, `postgresql`, `css-html`, `algorithms`, `browser-runtime`

Minimum 15 quiz questions per topic.

### Quiz question rules:
- 4 options per question
- Exactly one correct answer
- Options must be plausible — wrong options should be common misconceptions, not obviously wrong
- Explanation must clarify WHY the correct answer is correct AND why others are wrong

### Quiz JSON schema:

```json
[
  {
    "id": "javascript-quiz-1",
    "topicId": "javascript",
    "question": {
      "en": "What is the output of the following code?\n```js\nconsole.log(typeof null);\n```",
      "ru": "Что выведет следующий код?\n```js\nconsole.log(typeof null);\n```"
    },
    "options": {
      "en": ["\"null\"", "\"undefined\"", "\"object\"", "\"boolean\""],
      "ru": ["\"null\"", "\"undefined\"", "\"object\"", "\"boolean\""]
    },
    "correctIndex": 2,
    "explanation": {
      "en": "`typeof null` returns `\"object\"` — this is a well-known bug in JavaScript that was never fixed for backward compatibility reasons. `null` is a primitive, not an object.",
      "ru": "`typeof null` возвращает `\"object\"` — это известный баг JavaScript, который не был исправлен из соображений обратной совместимости. `null` — примитив, а не объект."
    }
  }
]
```

---

## EXECUTION ORDER

Run tasks in this order to avoid conflicts:

1. Task A — verify/fix existing RU markdown files
2. Task B — generate EN markdown translations
3. Task C — generate all questions JSONs (start with `javascript`, `react`, `typescript` — these are largest)
4. Task D — generate all tasks JSONs
5. Task E — generate all quiz JSONs

---

## OUTPUT VALIDATION

After generating all content, run these checks:

```bash
# Check all JSON files are valid
find content/ -name "*.json" | xargs -I {} node -e "JSON.parse(require('fs').readFileSync('{}', 'utf8')); console.log('OK: {}');"

# Count questions per topic
node -e "
const fs = require('fs');
const files = fs.readdirSync('content/questions');
files.forEach(f => {
  const data = JSON.parse(fs.readFileSync('content/questions/' + f, 'utf8'));
  console.log(f.replace('.json','') + ': ' + data.length + ' questions');
});
"
```

Fix any JSON parse errors before finishing.
