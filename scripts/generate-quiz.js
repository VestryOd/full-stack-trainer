#!/usr/bin/env node

/**
 * Full-Stack Trainer — Quiz Generator
 * Generates multiple-choice quiz questions for all topics using Anthropic API
 *
 * Usage:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-quiz.js
 *
 * Resume after interruption:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-quiz.js --resume
 *
 * Single topic:
 *   ANTHROPIC_API_KEY=sk-ant-... node generate-quiz.js --topic=javascript
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// ─── CONFIG ──────────────────────────────────────────────────────────────────

const API_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL = 'claude-haiku-4-5-20251001';
const QUIZ_DIR = path.join(__dirname, '..', 'content', 'quiz');
const PROGRESS_FILE = path.join(__dirname, '.quiz-progress.json');
const BATCH_SIZE = 5; // quiz questions per API call
const DELAY_MS = 1500;

if (!API_KEY) {
  console.error('❌  ANTHROPIC_API_KEY environment variable is not set');
  process.exit(1);
}

// ─── TOPIC DEFINITIONS ───────────────────────────────────────────────────────

const TOPICS = [
  {
    id: 'javascript',
    label: 'JavaScript',
    count: 50,
    areas: 'event loop, closures, prototype chain, this binding, hoisting, typeof/instanceof, async/await, promises, ES6+ features, coercion edge cases, scope, generators',
  },
  {
    id: 'typescript',
    label: 'TypeScript',
    count: 40,
    areas: 'type inference, interfaces vs types, generics, utility types, type guards, enums, conditional types, mapped types, strict mode behaviors',
  },
  {
    id: 'react',
    label: 'React',
    count: 50,
    areas: 'hooks rules, useState/useEffect behavior, reconciliation, key prop, memo/useMemo/useCallback, context, component lifecycle, controlled vs uncontrolled, Suspense',
  },
  {
    id: 'nextjs',
    label: 'Next.js',
    count: 30,
    areas: 'App Router vs Pages Router, Server vs Client components, data fetching strategies, caching layers, static vs dynamic rendering, middleware, image optimization',
  },
  {
    id: 'nodejs',
    label: 'Node.js',
    count: 50,
    areas: 'event loop phases, streams, process.nextTick vs setImmediate, cluster vs worker threads, CommonJS vs ESM, error handling, Buffer',
  },
  {
    id: 'nestjs',
    label: 'Nest.js',
    count: 30,
    areas: 'decorators, dependency injection, modules, guards vs interceptors vs pipes vs filters, lifecycle hooks, providers scope',
  },
  {
    id: 'postgresql',
    label: 'PostgreSQL',
    count: 30,
    areas: 'index types, EXPLAIN output, transaction isolation levels, MVCC, window functions, JOIN types, NULL behavior, VACUUM',
  },
  {
    id: 'css-html',
    label: 'CSS + HTML',
    count: 30,
    areas: 'specificity, box model, flexbox, grid, stacking context, pseudo-elements, BEM, CSS custom properties, semantic HTML, accessibility',
  },
  {
    id: 'algorithms',
    label: 'Algorithms & DS',
    count: 30,
    areas: 'Big O notation, sorting algorithms complexity, hash map operations, tree traversal, BFS vs DFS, dynamic programming concepts, space-time tradeoffs',
  },
  {
    id: 'browser-runtime',
    label: 'Browser / JS Runtime',
    count: 20,
    areas: 'rendering pipeline, reflow vs repaint, event delegation, Web APIs, CORS, storage types, service workers, critical rendering path',
  },
  {
    id: 'http-rest',
    label: 'HTTP / REST',
    count: 30,
    areas: 'HTTP methods, status codes, caching headers, CORS, REST constraints, idempotency, HTTP/2 features, authentication methods',
  },
  {
    id: 'testing',
    label: 'Testing',
    count: 15,
    areas: 'unit vs integration vs e2e, mock vs stub vs spy, testing pyramid, coverage metrics, async testing, React Testing Library queries',
  },
  {
    id: 'security',
    label: 'Security',
    count: 25,
    areas: 'XSS types, CSRF, SQL injection, JWT structure, OAuth 2.0 flows, CSP headers, cookie flags, HTTPS/TLS',
  },
  {
    id: 'solid-grasp',
    label: 'SOLID + GRASP',
    count: 25,
    areas: 'SRP, OCP, LSP, ISP, DIP — recognizing violations, GRASP patterns, applying principles to real code examples',
  },
  {
    id: 'oop-patterns',
    label: 'OOP Patterns',
    count: 25,
    areas: 'pattern identification, Singleton pitfalls, Factory vs Abstract Factory, Observer vs Pub/Sub, Strategy vs State, Decorator vs HOC',
  },
  {
    id: 'git',
    label: 'Git',
    count: 20,
    areas: 'rebase vs merge, cherry-pick, reflog, git objects (blob/tree/commit), fast-forward, detached HEAD, stash behavior',
  },
  {
    id: 'docker',
    label: 'Docker',
    count: 15,
    areas: 'image vs container, layers, multi-stage builds, volume types, network modes, docker-compose, CMD vs ENTRYPOINT',
  },
  {
    id: 'web-performance',
    label: 'Web Performance',
    count: 20,
    areas: 'Core Web Vitals definitions, LCP/CLS/INP, lazy loading, code splitting, preload vs prefetch, render-blocking resources, image formats',
  },
  {
    id: 'graphql',
    label: 'GraphQL',
    count: 25,
    areas: 'queries vs mutations vs subscriptions, schema types, N+1 problem, fragments, Apollo Client cache, introspection, REST vs GraphQL tradeoffs',
  },
  {
    id: 'architecture',
    label: 'Architecture Patterns',
    count: 20,
    areas: 'Clean vs Hexagonal vs Layered, CQRS concepts, event sourcing basics, repository pattern, dependency inversion in practice',
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

function loadQuiz(topicId) {
  const file = path.join(QUIZ_DIR, `${topicId}.json`);
  if (!fs.existsSync(file)) return [];
  try {
    const content = fs.readFileSync(file, 'utf8').trim();
    if (!content || content === '[]') return [];
    return JSON.parse(content);
  } catch {
    return [];
  }
}

function saveQuiz(topicId, questions) {
  const file = path.join(QUIZ_DIR, `${topicId}.json`);
  fs.writeFileSync(file, JSON.stringify(questions, null, 2));
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

function buildPrompt(topic, startIndex, chunkSize) {
  const codeExample = 'What is logged?\\n```js\\nconsole.log(typeof null);\\n```';
  return `Generate exactly ${chunkSize} multiple-choice quiz questions for a Senior Fullstack Engineer interview preparation tool.

Topic: ${topic.label}
Areas to cover: ${topic.areas}

IDs must start from: ${topic.id}-quiz-${startIndex + 1}

Return ONLY a valid JSON array. No explanation, no markdown fences. Just the raw JSON array starting with [.

Schema for each question:
{
  "id": "${topic.id}-quiz-${startIndex + 1}",
  "topicId": "${topic.id}",
  "question": {
    "en": "The question text in English. Can include a short code snippet inline if needed.",
    "ru": "Текст вопроса на русском языке."
  },
  "options": {
    "en": ["Option A", "Option B", "Option C", "Option D"],
    "ru": ["Вариант А", "Вариант Б", "Вариант В", "Вариант Г"]
  },
  "correctIndex": 0,
  "explanation": {
    "en": "Why the correct answer is correct, and why the other options are wrong. 2-3 sentences.",
    "ru": "Почему правильный ответ верный, и почему остальные варианты неверны. 2-3 предложения."
  }
}

Critical rules:
- correctIndex must be 0, 1, 2, or 3 — the index of the correct answer in the options array
- Distribute correctIndex evenly across questions — don't always use 0
- All 4 options must be plausible — wrong options should be common misconceptions, not obviously wrong
- Options order in en and ru must match (ru[0] is translation of en[0], etc.)
- Questions must test UNDERSTANDING, not memorization of syntax
- Include at least 2 questions with short code snippets to read and predict output
- Both en and ru fields must be fully translated — no placeholders
- Questions must be distinct — cover different sub-topics from the areas list
- If the question contains a code snippet, NEVER put it inline. ALWAYS format as markdown code block with triple backticks and language tag. Example: "${codeExample}"
- The \\\\n before opening backticks and after closing backticks are required.

Generate exactly ${chunkSize} questions now:`;
}

// ─── GENERATE CHUNK ──────────────────────────────────────────────────────────

async function generateTopic(topic, progress) {
  const totalNeeded = topic.count;
  const chunks = Math.ceil(totalNeeded / BATCH_SIZE);
  let startIndex = loadQuiz(topic.id).length;

  for (let i = 0; i < chunks; i++) {
    const chunkKey = `${topic.id}:chunk${i}`;

    if (progress[chunkKey] === 'done') {
      console.log(`  ⏭  Skipping ${chunkKey} (already done)`);
      startIndex += BATCH_SIZE;
      continue;
    }

    const chunkSize = Math.min(BATCH_SIZE, totalNeeded - i * BATCH_SIZE);
    console.log(`  ⚙  Generating ${chunkSize} questions for ${topic.label} (chunk ${i + 1}/${chunks})...`);

    const prompt = buildPrompt(topic, startIndex, chunkSize);

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

        // Validate structure
        for (const q of newQuestions) {
          if (!q.id) throw new Error('Missing id');
          if (!q.question?.en || !q.question?.ru) throw new Error(`Missing question text in ${q.id}`);
          if (!Array.isArray(q.options?.en) || q.options.en.length !== 4) throw new Error(`options.en must have 4 items in ${q.id}`);
          if (!Array.isArray(q.options?.ru) || q.options.ru.length !== 4) throw new Error(`options.ru must have 4 items in ${q.id}`);
          if (typeof q.correctIndex !== 'number' || q.correctIndex < 0 || q.correctIndex > 3) throw new Error(`Invalid correctIndex in ${q.id}`);
          if (!q.explanation?.en || !q.explanation?.ru) throw new Error(`Missing explanation in ${q.id}`);
        }

        const existing = loadQuiz(topic.id);
        const merged = [...existing, ...newQuestions];
        saveQuiz(topic.id, merged);

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

// ─── MAIN ────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const resumeMode = args.includes('--resume');
  const singleTopic = args.find(a => a.startsWith('--topic='))?.split('=')[1];

  console.log('🚀 Full-Stack Trainer — Quiz Generator');
  console.log(`   Model: ${MODEL}`);
  console.log(`   Mode: ${resumeMode ? 'resume' : 'fresh start'}${singleTopic ? ` (topic: ${singleTopic})` : ''}`);
  console.log('');

  if (!fs.existsSync(QUIZ_DIR)) {
    fs.mkdirSync(QUIZ_DIR, { recursive: true });
    console.log(`   Created directory: ${QUIZ_DIR}\n`);
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

  const totalTarget = topicsToProcess.reduce((sum, t) => sum + t.count, 0);
  console.log(`   Target: ${totalTarget} quiz questions across ${topicsToProcess.length} topics\n`);

  let totalGenerated = 0;

  for (const topic of topicsToProcess) {
    const existing = loadQuiz(topic.id);
    console.log(`\n📚 ${topic.label} (${existing.length}/${topic.count} existing)`);
    await generateTopic(topic, progress);
    const final = loadQuiz(topic.id);
    totalGenerated += final.length;
    console.log(`  📊 ${topic.label} complete: ${final.length} questions`);
  }

  console.log('\n' + '═'.repeat(50));
  console.log(`✅  Generation complete!`);
  console.log(`   Total quiz questions: ${totalGenerated} / ${totalTarget} target`);
  console.log('');

  // Validation
  console.log('🔍 Validating all files...');
  let hasErrors = false;

  for (const topic of TOPICS) {
    const file = path.join(QUIZ_DIR, `${topic.id}.json`);
    if (!fs.existsSync(file)) {
      console.log(`  ⚠  Missing: ${topic.id}.json`);
      hasErrors = true;
      continue;
    }

    const questions = loadQuiz(topic.id);
    const issues = questions.filter(q =>
      !q.id ||
      !q.question?.en ||
      !q.question?.ru ||
      !Array.isArray(q.options?.en) ||
      q.options.en.length !== 4 ||
      typeof q.correctIndex !== 'number' ||
      !q.explanation?.en
    );

    if (issues.length > 0) {
      console.log(`  ⚠  ${topic.id}.json: ${issues.length} invalid questions`);
      hasErrors = true;
    } else {
      console.log(`  ✓  ${topic.id}.json: ${questions.length} questions`);
    }
  }

  if (!hasErrors) {
    console.log('\n✅  All quiz files valid!');
  } else {
    console.log('\n⚠  Some files have issues. Run with --resume to retry.');
    console.log('\nTo clean invalid entries:');
    console.log(`node -e "
const fs=require('fs');
const dir='content/quiz';
fs.readdirSync(dir).forEach(f=>{
  const fp=dir+'/'+f;
  const d=JSON.parse(fs.readFileSync(fp,'utf8'));
  const v=d.filter(q=>q.id&&q.question?.en&&Array.isArray(q.options?.en)&&q.options.en.length===4&&typeof q.correctIndex==='number');
  fs.writeFileSync(fp,JSON.stringify(v,null,2));
  console.log(f+': kept '+v.length);
});
"`);
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
