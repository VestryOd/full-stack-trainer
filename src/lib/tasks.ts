import fs from 'fs';
import path from 'path';
import type { Task } from '@/types';

const TASKS_DIR = path.join(process.cwd(), 'content', 'tasks');

function readTopicTasks(topicId: string): Task[] {
  const filePath = path.join(TASKS_DIR, `${topicId}.json`);
  if (!fs.existsSync(filePath)) return [];
  const raw = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as Task[];
}

export function getTasksByTopic(topicId: string): Task[] {
  return readTopicTasks(topicId);
}

export function getAllTasks(): Task[] {
  if (!fs.existsSync(TASKS_DIR)) return [];
  const files = fs.readdirSync(TASKS_DIR).filter((f) => f.endsWith('.json'));
  return files.flatMap((file) => {
    const raw = fs.readFileSync(path.join(TASKS_DIR, file), 'utf-8');
    return JSON.parse(raw) as Task[];
  });
}

export function getTaskById(topicId: string, taskId: string): Task | null {
  const tasks = getTasksByTopic(topicId);
  return tasks.find((t) => t.id === taskId) ?? null;
}
