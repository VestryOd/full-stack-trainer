import type { Task } from '@/types';
import { fisherYates } from './quiz-utils';

/**
 * Random task sets are a *playlist of ids* laid over the task pages that already
 * exist, not a new way to render a task.
 *
 * The quiz can afford to build its questions on the client because a question is a
 * few hundred bytes. A task carries starter code, a full solution and both locales,
 * so shipping the pool to the browser would cost megabytes and would mean
 * re-implementing the shiki rendering that `/tasks/[topicId]/[taskId]` already does
 * on the server. So the picker only ever chooses ids and navigates.
 */

export interface TaskRef {
  id: string;
  topicId: string;
  difficulty: Task['difficulty'];
}

export interface TaskPlaylist {
  /** The chosen tasks, in the order they will be shown. */
  refs: TaskRef[];
  /** Topics the set was drawn from — shown as a badge while the set is active. */
  topicIds: string[];
}

export const TASK_PLAYLIST_KEY = 'fst-tasks-random';

export function href(ref: TaskRef): string {
  return `/tasks/${ref.topicId}/${ref.id}`;
}

export function savePlaylist(playlist: TaskPlaylist): void {
  sessionStorage.setItem(TASK_PLAYLIST_KEY, JSON.stringify(playlist));
}

export function clearPlaylist(): void {
  sessionStorage.removeItem(TASK_PLAYLIST_KEY);
}

/** Returns null when there is no set, or when what is stored is not one. */
export function loadPlaylist(): TaskPlaylist | null {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(TASK_PLAYLIST_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as TaskPlaylist;
    if (!Array.isArray(parsed.refs) || parsed.refs.length === 0) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function buildPlaylist(index: TaskRef[], topicIds: string[], count: number): TaskPlaylist {
  const wanted = new Set(topicIds);
  const pool = index.filter((ref) => wanted.has(ref.topicId));
  return { refs: fisherYates(pool).slice(0, count), topicIds };
}

/**
 * A random task, never the one already open. Falls back to the current task only
 * when it is the single candidate — better to re-show it than to navigate nowhere.
 */
export function pickRandom(index: TaskRef[], topicId?: string, excludeId?: string): TaskRef | null {
  const scoped = topicId ? index.filter((ref) => ref.topicId === topicId) : index;
  if (scoped.length === 0) return null;
  const candidates = scoped.filter((ref) => ref.id !== excludeId);
  const pool = candidates.length > 0 ? candidates : scoped;
  return pool[Math.floor(Math.random() * pool.length)];
}
