import type { Course } from '@/types';

export const COURSES: readonly Course[] = [
  { id: 'python-fullstack', label: 'Python for Fullstack Engineers', level: 'deep' },
] as const;

export const COURSE_IDS = COURSES.map((c) => c.id);

export function getCourseById(id: string): Course | undefined {
  return COURSES.find((c) => c.id === id);
}
