import fs from 'fs';
import path from 'path';
import type { QuizQuestion } from '@/types';

const QUIZ_DIR = path.join(process.cwd(), 'content', 'quiz');

function readTopicQuiz(topicId: string): QuizQuestion[] {
  const filePath = path.join(QUIZ_DIR, `${topicId}.json`);
  if (!fs.existsSync(filePath)) return [];
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as QuizQuestion[];
}

function shuffled<T>(arr: T[]): T[] {
  return [...arr].sort(() => Math.random() - 0.5);
}

function dedupeById(questions: QuizQuestion[]): QuizQuestion[] {
  const seen = new Set<string>();
  return questions.filter((q) => {
    if (seen.has(q.id)) return false;
    seen.add(q.id);
    return true;
  });
}

export function getAvailableQuizTopics(): string[] {
  if (!fs.existsSync(QUIZ_DIR)) return [];
  return fs
    .readdirSync(QUIZ_DIR)
    .filter((f) => f.endsWith('.json'))
    .map((f) => f.replace(/\.json$/, ''));
}

export function getQuizQuestions(topicIds?: string[], count?: number): QuizQuestion[] {
  const topics = topicIds ?? getAvailableQuizTopics();
  const pool = topics.flatMap((topicId) => readTopicQuiz(topicId));
  const selected = shuffled(dedupeById(pool));
  return count !== undefined ? selected.slice(0, count) : selected;
}
