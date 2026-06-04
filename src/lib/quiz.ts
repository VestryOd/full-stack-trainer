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

export function getQuizByTopic(topicId: string): QuizQuestion[] {
  return readTopicQuiz(topicId);
}

export function getAllQuizQuestions(): QuizQuestion[] {
  if (!fs.existsSync(QUIZ_DIR)) return [];
  const files = fs.readdirSync(QUIZ_DIR).filter((f) => f.endsWith('.json'));
  return files.flatMap((file) => {
    const raw = fs.readFileSync(path.join(QUIZ_DIR, file), 'utf-8');
    return JSON.parse(raw) as QuizQuestion[];
  });
}

export function getRandomQuizQuestions(n: number, topicId?: string): QuizQuestion[] {
  const pool = topicId ? getQuizByTopic(topicId) : getAllQuizQuestions();
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}
