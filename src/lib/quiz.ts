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

function fisherYates<T>(arr: T[]): T[] {
  const result = [...arr];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function shuffleOptions(question: QuizQuestion): QuizQuestion {
  const len = question.options.en.length;
  const perm = Array.from({ length: len }, (_, i) => i);
  for (let i = len - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [perm[i], perm[j]] = [perm[j], perm[i]];
  }
  return {
    ...question,
    options: {
      en: perm.map((i) => question.options.en[i]),
      ru: perm.map((i) => (question.options.ru ?? question.options.en)[i]),
    },
    correctIndex: perm.indexOf(question.correctIndex),
  };
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

export function getTopicQuestionCount(topicId: string): number {
  return readTopicQuiz(topicId).length;
}

export function getQuizQuestions(topicIds?: string[], count?: number): QuizQuestion[] {
  const topics = topicIds ?? getAvailableQuizTopics();
  const pool = topics.flatMap((topicId) => readTopicQuiz(topicId));
  const selected = fisherYates(dedupeById(pool));
  const sliced = count !== undefined ? selected.slice(0, count) : selected;
  return sliced.map(shuffleOptions);
}
