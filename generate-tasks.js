#!/usr/bin/env node

/**
 * Full-Stack Trainer — Tasks Generator
 * Generates coding tasks for all topics using Anthropic API
 *
 * Usage:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-tasks.js
 *
 * Resume after interruption:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-tasks.js --resume
 *
 * Single topic:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-tasks.js --topic=javascript
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// ─── CONFIG ──────────────────────────────────────────────────────────────────

const API_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL = 'claude-haiku-4-5-20251001';
const TASKS_DIR = path.join(__dirname, 'content', 'tasks');
const PROGRESS_FILE = path.join(__dirname, '.tasks-progress.json');
const BATCH_SIZE = 3; // tasks per API call (tasks are longer than questions)
const DELAY_MS = 2000;

if (!API_KEY) {
  console.error('❌  ANTHROPIC_API_KEY environment variable is not set');
  process.exit(1);
}

// ─── TOPIC DEFINITIONS ───────────────────────────────────────────────────────

const TOPICS = [
  {
    id: 'javascript',
    label: 'JavaScript',
    batches: [
      {
        difficulty: 'easy',
        count: 6,
        areas: 'array methods (map/filter/reduce), string manipulation, basic object operations, simple closures, typeof checks',
      },
      {
        difficulty: 'medium',
        count: 10,
        areas: 'debounce, throttle, deepClone, EventEmitter class, Promise.all from scratch, curry function, pipe/compose, flatten nested array, memoization with Map, LRU Cache class',
      },
      {
        difficulty: 'hard',
        count: 6,
        areas: 'async queue with concurrency limit, observable pattern, cancellable promise, deep merge objects, virtual DOM diff algorithm concept, scheduler with priority',
      },
    ],
  },
  {
    id: 'typescript',
    label: 'TypeScript',
    batches: [
      {
        difficulty: 'easy',
        count: 4,
        areas: 'basic generics, simple utility types usage, type guards, function overloads',
      },
      {
        difficulty: 'medium',
        count: 6,
        areas: 'implement DeepReadonly, implement DeepPartial, type-safe EventEmitter with generic event map, implement Pick and Omit from scratch, conditional types with infer, builder pattern with method chaining types',
      },
      {
        difficulty: 'hard',
        count: 4,
        areas: 'implement Awaited from scratch, recursive type for JSON, phantom types for validated data, type-safe router with params extraction',
      },
    ],
  },
  {
    id: 'react',
    label: 'React',
    batches: [
      {
        difficulty: 'easy',
        count: 4,
        areas: 'controlled input component, toggle component, counter with useReducer, simple custom hook',
      },
      {
        difficulty: 'medium',
        count: 6,
        areas: 'useDebounce hook, usePrevious hook, useLocalStorage hook, useIntersectionObserver hook, infinite scroll component, virtualized list (render only visible items)',
      },
      {
        difficulty: 'hard',
        count: 4,
        areas: 'form builder with validation without libraries, compound components pattern, render props + hooks migration, context with performance optimization (no unnecessary re-renders)',
      },
    ],
  },
  {
    id: 'nodejs',
    label: 'Node.js',
    batches: [
      {
        difficulty: 'easy',
        count: 3,
        areas: 'read and parse JSON file, simple HTTP server without frameworks, environment config loader',
      },
      {
        difficulty: 'medium',
        count: 5,
        areas: 'rate limiter middleware, file upload with streams, simple job queue with concurrency, middleware pipeline (like Express but from scratch), graceful shutdown handler',
      },
      {
        difficulty: 'hard',
        count: 3,
        areas: 'worker threads pool, circuit breaker pattern, async local storage for request context tracing',
      },
    ],
  },
  {
    id: 'algorithms',
    label: 'Algorithms & DS',
    batches: [
      {
        difficulty: 'easy',
        count: 6,
        areas: 'Two Sum, Valid Parentheses, Reverse String, Fibonacci with memoization, FizzBuzz variants, find duplicates in array',
      },
      {
        difficulty: 'medium',
        count: 10,
        areas: 'Binary Search, Maximum Subarray (Kadane), Group Anagrams, Merge Intervals, Linked List cycle detection, BFS/DFS on graph, implement Stack using queues, find missing number, product of array except self, longest common prefix',
      },
      {
        difficulty: 'hard',
        count: 6,
        areas: 'LRU Cache, Serialize/Deserialize Binary Tree, Merge K Sorted Lists, Trapping Rain Water, Word Ladder BFS, First Missing Positive',
      },
    ],
  },
  {
    id: 'css-html',
    label: 'CSS + HTML',
    batches: [
      {
        difficulty: 'easy',
        count: 3,
        areas: 'centered div (multiple methods), responsive navbar, simple card component',
      },
      {
        difficulty: 'medium',
        count: 5,
        areas: 'CSS-only accordion, sticky header that changes on scroll (JS allowed), CSS Grid magazine layout, custom checkbox/radio styles, skeleton loading animation',
      },
      {
        difficulty: 'hard',
        count: 3,
        areas: 'CSS-only carousel, accessible modal dialog from scratch, responsive data table with frozen first column',
      },
    ],
  },
  {
    id: 'testing',
    label: 'Testing',
    batches: [
      {
        difficulty: 'easy',
        count: 3,
        areas: 'unit test for pure function, test async function with Jest, mock module dependency',
      },
      {
        difficulty: 'medium',
        count: 5,
        areas: 'test React component with RTL (user events, async updates), mock fetch/API calls with MSW concept, test custom hook with renderHook, integration test for form submission, test error boundary behavior',
      },
      {
        difficulty: 'hard',
        count: 3,
        areas: 'test component with complex state machine, property-based testing concept, test for race conditions in async code',
      },
    ],
  },
  {
    id: 'graphql',
    label: 'GraphQL',
    batches: [
      {
        difficulty: 'easy',
        count: 3,
        areas: 'write a basic Query schema and resolver, useQuery hook with loading/error states, fragment definition and reuse',
      },
      {
        difficulty: 'medium',
        count: 4,
        areas: 'implement useMutation with optimistic update, DataLoader for N+1 batching, pagination with cursor-based approach, Apollo Client cache update after mutation',
      },
      {
        difficulty: 'hard',
        count: 3,
        areas: 'implement subscription with WebSocket, schema-first type generation setup, error handling with partial responses',
      },
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
      max_tokens: 16000,
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

function loadTasks(topicId) {
  const file = path.join(TASKS_DIR, `${topicId}.json`);
  if (!fs.existsSync(file)) return [];
  try {
    const content = fs.readFileSync(file, 'utf8').trim();
    if (!content || content === '[]') return [];
    return JSON.parse(content);
  } catch {
    return [];
  }
}

function saveTasks(topicId, tasks) {
  const file = path.join(TASKS_DIR, `${topicId}.json`);
  fs.writeFileSync(file, JSON.stringify(tasks, null, 2));
}

function extractJSON(text) {
  let cleaned = text
    .replace(/```json\s*/g, '')
    .replace(/```\s*/g, '')
    .trim();

  try {
    return JSON.parse(cleaned);
  } catch {}

  const start = cleaned.indexOf('[');
  const end = cleaned.lastIndexOf(']');
  if (start !== -1 && end !== -1 && end > start) {
    return JSON.parse(cleaned.slice(start, end + 1));
  }

  throw new Error('No valid JSON array found in response');
}

// ─── PROMPT BUILDER ──────────────────────────────────────────────────────────

function buildPrompt(topic, batch, startIndex, chunkSize) {
  return `Generate exactly ${chunkSize} coding tasks for a Senior Fullstack Engineer interview preparation tool.

Topic: ${topic.label}
Difficulty: ${batch.difficulty}
Task areas: ${batch.areas}

IDs must start from: ${topic.id}-t-${startIndex + 1}

Return ONLY a valid JSON array. No explanation, no markdown fences, no backticks wrapping the array. Just the raw JSON array starting with [.

Schema for each task object:
{
  "id": "${topic.id}-t-${startIndex + 1}",
  "topicId": "${topic.id}",
  "difficulty": "${batch.difficulty}",
  "title": {
    "en": "Short task title in English",
    "ru": "Короткое название задачи на русском"
  },
  "description": {
    "en": "Full task description with requirements and example usage in markdown. Include:\\n- What to implement\\n- Function/class signature\\n- Example input/output\\n- Edge cases to handle",
    "ru": "Полное описание задачи на русском языке в том же формате."
  },
  "starterCode": "// TypeScript or JavaScript starter code\\n// with function signature and comments\\nfunction example(input: string): string {\\n  // implement here\\n}",
  "solution": "// Complete working solution\\nfunction example(input: string): string {\\n  return input.split('').reverse().join('');\\n}",
  "solutionExplanation": {
    "en": "**Approach:** Brief explanation of the algorithm/pattern used.\\n\\n**Time complexity:** O(n)\\n**Space complexity:** O(n)\\n\\n**Common mistakes:**\\n- Mistake 1\\n- Mistake 2",
    "ru": "**Подход:** Краткое объяснение алгоритма/паттерна.\\n\\n**Временная сложность:** O(n)\\n**Пространственная сложность:** O(n)\\n\\n**Типичные ошибки:**\\n- Ошибка 1\\n- Ошибка 2"
  },
  "tags": ["specific-tag-1", "specific-tag-2"]
}

Rules:
- starterCode must be valid TypeScript with correct types (use JS if topic is css-html or graphql SDL)
- solution must be a complete, working, correct implementation — no pseudocode
- Both solution and starterCode are plain strings with \\n for newlines, NO nested code fences
- description must include at least one concrete example with input → output
- solutionExplanation must include time and space complexity
- Both en and ru fields must be complete — no placeholders
- Tags must be specific to the algorithm/pattern used
- Tasks must be distinct — no duplicates within the batch

Generate exactly ${chunkSize} tasks now:`;
}

// ─── GENERATE BATCH ──────────────────────────────────────────────────────────

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
    console.log(`  ⚙  Generating ${chunkSize} ${batch.difficulty} tasks for ${topic.label} (chunk ${i + 1}/${chunks})...`);

    const prompt = buildPrompt(topic, batch, startIndex, chunkSize);

    let attempts = 0;
    const maxAttempts = 3;
    let success = false;

    while (attempts < maxAttempts) {
      attempts++;
      try {
        const response = await callAnthropicAPI(prompt);
        const newTasks = extractJSON(response);

        if (!Array.isArray(newTasks) || newTasks.length === 0) {
          throw new Error('Response is not a valid array');
        }

        // Validate required fields
        const first = newTasks[0];
        if (!first.id || !first.title?.en || !first.solution || !first.starterCode) {
          throw new Error(`Task missing required fields: ${JSON.stringify(Object.keys(first))}`);
        }

        const existing = loadTasks(topic.id);
        const merged = [...existing, ...newTasks];
        saveTasks(topic.id, merged);

        progress[chunkKey] = 'done';
        saveProgress(progress);

        console.log(`  ✓  Added ${newTasks.length} tasks → ${topic.id}.json now has ${merged.length}`);
        startIndex += newTasks.length;
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

// ─── MAIN ────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const resumeMode = args.includes('--resume');
  const singleTopic = args.find(a => a.startsWith('--topic='))?.split('=')[1];

  console.log('🚀 Full-Stack Trainer — Tasks Generator');
  console.log(`   Model: ${MODEL}`);
  console.log(`   Mode: ${resumeMode ? 'resume' : 'fresh start'}${singleTopic ? ` (topic: ${singleTopic})` : ''}`);
  console.log('');

  // Ensure tasks directory exists
  if (!fs.existsSync(TASKS_DIR)) {
    fs.mkdirSync(TASKS_DIR, { recursive: true });
    console.log(`   Created directory: ${TASKS_DIR}`);
  }

  const progress = resumeMode ? loadProgress() : {};
  if (!resumeMode) saveProgress({});

  const topicsToProcess = singleTopic
    ? TOPICS.filter(t => t.id === singleTopic)
    : TOPICS;

  if (singleTopic && topicsToProcess.length === 0) {
    console.error(`❌  Topic "${singleTopic}" not found`);
    console.error(`    Available: ${TOPICS.map(t => t.id).join(', ')}`);
    process.exit(1);
  }

  const totalTarget = topicsToProcess.reduce(
    (sum, t) => sum + t.batches.reduce((s, b) => s + b.count, 0),
    0
  );

  console.log(`   Target: ${totalTarget} tasks across ${topicsToProcess.length} topics\n`);

  let totalGenerated = 0;

  for (const topic of topicsToProcess) {
    const existing = loadTasks(topic.id);
    const topicTarget = topic.batches.reduce((s, b) => s + b.count, 0);
    console.log(`\n📚 ${topic.label} (${existing.length}/${topicTarget} existing)`);

    let currentIndex = existing.length;

    for (const batch of topic.batches) {
      await generateBatch(topic, batch, currentIndex, progress);
      currentIndex += batch.count;
    }

    const final = loadTasks(topic.id);
    totalGenerated += final.length;
    console.log(`  📊 ${topic.label} complete: ${final.length} tasks`);
  }

  console.log('\n' + '═'.repeat(50));
  console.log(`✅  Generation complete!`);
  console.log(`   Total tasks: ${totalGenerated} / ${totalTarget} target`);
  console.log('');

  // Final validation
  console.log('🔍 Validating all files...');
  let hasErrors = false;

  for (const topic of TOPICS) {
    const file = path.join(TASKS_DIR, `${topic.id}.json`);
    if (!fs.existsSync(file)) {
      console.log(`  ⚠  Missing: ${topic.id}.json`);
      hasErrors = true;
      continue;
    }

    const tasks = loadTasks(topic.id);
    const issues = tasks.filter(
      t => !t.id || !t.title?.en || !t.solution || !t.starterCode || !t.description?.en
    );

    if (issues.length > 0) {
      console.log(`  ⚠  ${topic.id}.json: ${issues.length} tasks with missing fields (ids: ${issues.map(t => t.id).join(', ')})`);
      hasErrors = true;
    } else {
      console.log(`  ✓  ${topic.id}.json: ${tasks.length} tasks`);
    }
  }

  if (!hasErrors) {
    console.log('\n✅  All files valid!');
  } else {
    console.log('\n⚠  Some files have issues. Run with --resume to retry failed chunks.');
    console.log('   To remove invalid tasks run:');
    console.log(`   node -e "
const fs=require('fs');
['javascript','typescript','react','nodejs','algorithms','css-html','testing','graphql'].forEach(t=>{
  const f='content/tasks/'+t+'.json';
  if(!fs.existsSync(f)) return;
  const d=JSON.parse(fs.readFileSync(f,'utf8'));
  const v=d.filter(q=>q.id&&q.title?.en&&q.solution&&q.starterCode);
  fs.writeFileSync(f,JSON.stringify(v,null,2));
  console.log(t+': kept '+v.length);
});
"`);
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
