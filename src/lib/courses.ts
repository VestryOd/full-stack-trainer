import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import type { CourseChapter, Locale } from '@/types';

const CONTENT_DIR = path.join(process.cwd(), 'content', 'courses');

export function getChaptersForCourse(courseId: string, locale: Locale): CourseChapter[] {
  const dir = path.join(CONTENT_DIR, courseId, locale);

  if (!fs.existsSync(dir)) return [];

  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.md'));

  return files
    .map((file) => {
      const raw = fs.readFileSync(path.join(dir, file), 'utf-8');
      const { data, content } = matter(raw);
      const slug = file.replace(/\.md$/, '');
      const title = (data.title as string | undefined) ?? slug;
      return { courseId, slug, title, content, locale };
    })
    .sort((a, b) => a.slug.localeCompare(b.slug));
}

export function getChapter(courseId: string, slug: string, locale: Locale): CourseChapter | null {
  const filePath = path.join(CONTENT_DIR, courseId, locale, `${slug}.md`);

  if (!fs.existsSync(filePath)) return null;

  const raw = fs.readFileSync(filePath, 'utf-8');
  const { data, content } = matter(raw);
  const title = (data.title as string | undefined) ?? slug;
  return { courseId, slug, title, content, locale };
}

export function getCourseChapterCount(courseId: string): number {
  const ruCount = getSlugsForCourse(courseId, 'ru').length;
  return ruCount > 0 ? ruCount : getSlugsForCourse(courseId, 'en').length;
}

export function getSlugsForCourse(courseId: string, locale: Locale): string[] {
  const dir = path.join(CONTENT_DIR, courseId, locale);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.md'))
    .map((f) => f.replace(/\.md$/, ''));
}
