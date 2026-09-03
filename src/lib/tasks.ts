import fs from 'fs';
import path from 'path';
import type { Task } from '@/types';
import type { TaskRef } from './tasks-random';

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

/**
 * Id-only view of every task, for the random-picker routes.
 *
 * A task carries its starter code, solution and both locales of everything else, so
 * the full set is megabytes. The random routes only ever need to pick an id and
 * navigate to the page that already exists for it, so they get this instead.
 */
export function getTaskIndex(): TaskRef[] {
  return getAllTasks().map((task) => ({
    id: task.id,
    topicId: task.topicId,
    difficulty: task.difficulty,
  }));
}
