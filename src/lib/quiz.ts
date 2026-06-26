import fs from 'fs';
import path from 'path';
import type { QuizQuestion } from '@/types';
import { fisherYates, shuffleOptions, dedupeById } from './quiz-utils';

const QUIZ_DIR = path.join(process.cwd(), 'content', 'quiz');

function readTopicQuiz(topicId: string): QuizQuestion[] {
  const filePath = path.join(QUIZ_DIR, `${topicId}.json`);
  if (!fs.existsSync(filePath)) return [];
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as QuizQuestion[];
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

export function getAllQuizQuestionsPerTopic(): Record<string, QuizQuestion[]> {
  const result: Record<string, QuizQuestion[]> = {};
  for (const topicId of getAvailableQuizTopics()) {
    result[topicId] = readTopicQuiz(topicId);
  }
  return result;
}
