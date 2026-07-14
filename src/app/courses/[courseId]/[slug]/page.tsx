import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { COURSES, getCourseById } from '@/constants/courses';
import { getChapter, getSlugsForCourse } from '@/lib/courses';
import { renderArticleHtml } from '@/components/theory/ArticleRenderer';
import { ChapterView } from '@/components/courses/ChapterView';

interface Props {
  params: { courseId: string; slug: string };
}

export function generateMetadata({ params }: Props): Metadata {
  const chapter = getChapter(params.courseId, params.slug, 'en') ?? getChapter(params.courseId, params.slug, 'ru');
  if (!chapter) return {};
  return { title: chapter.title };
}

export async function generateStaticParams() {
  const params: { courseId: string; slug: string }[] = [];
  for (const course of COURSES) {
    const slugsRu = getSlugsForCourse(course.id, 'ru');
    const slugsEn = getSlugsForCourse(course.id, 'en');
    const seen = new Set<string>();
    const allSlugs = [...slugsRu, ...slugsEn].filter((s) => {
      if (seen.has(s)) return false;
      seen.add(s);
      return true;
    });
    for (const slug of allSlugs) {
      params.push({ courseId: course.id, slug });
    }
  }
  return params;
}

export default async function ChapterPage({ params }: Props) {
  const course = getCourseById(params.courseId);
  if (!course) notFound();

  const chapterRu = getChapter(params.courseId, params.slug, 'ru');
  const chapterEn = getChapter(params.courseId, params.slug, 'en');
  if (!chapterRu && !chapterEn) notFound();

  // Pre-render both locales on the server
  const [htmlEn, htmlRu] = await Promise.all([
    chapterEn ? renderArticleHtml(chapterEn.content) : Promise.resolve(null),
    chapterRu ? renderArticleHtml(chapterRu.content) : Promise.resolve(null),
  ]);

  // Navigation slugs
  const slugsRu = getSlugsForCourse(params.courseId, 'ru');
  const slugsEn = getSlugsForCourse(params.courseId, 'en');
  const slugs = slugsRu.length > 0 ? slugsRu : slugsEn;

  const idx = slugs.indexOf(params.slug);
  const prevSlug = idx > 0 ? slugs[idx - 1] : null;
  const nextSlug = idx < slugs.length - 1 ? slugs[idx + 1] : null;

  return (
    <ChapterView
      courseId={params.courseId}
      courseLabel={course.label}
      slug={params.slug}
      htmlEn={htmlEn}
      htmlRu={htmlRu}
      prevSlug={prevSlug}
      nextSlug={nextSlug}
    />
  );
}
