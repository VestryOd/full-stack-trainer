import fs from 'fs';
import path from 'path';
import type { Question } from '@/types';

const QUESTIONS_DIR = path.join(process.cwd(), 'content', 'questions');

function readTopicQuestions(topicId: string): Question[] {
  const filePath = path.join(QUESTIONS_DIR, `${topicId}.json`);
  if (!fs.existsSync(filePath)) return [];
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as Question[];
}

export function getQuestionsByTopic(topicId: string): Question[] {
  return readTopicQuestions(topicId);
}

export function getAllQuestions(): Question[] {
  if (!fs.existsSync(QUESTIONS_DIR)) return [];
  const files = fs.readdirSync(QUESTIONS_DIR).filter((f) => f.endsWith('.json'));
  return files.flatMap((file) => {
    const raw = fs.readFileSync(path.join(QUESTIONS_DIR, file), 'utf-8');
    return JSON.parse(raw) as Question[];
  });
}

export function getRandomQuestions(n: number, topicId?: string): Question[] {
  const pool = topicId ? getQuestionsByTopic(topicId) : getAllQuestions();
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}
