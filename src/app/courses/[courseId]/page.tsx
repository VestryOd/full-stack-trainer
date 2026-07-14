import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { COURSES, getCourseById } from '@/constants/courses';
import { getChaptersForCourse } from '@/lib/courses';
import { CourseChaptersView } from '@/components/courses/CourseChaptersView';

interface Props {
  params: { courseId: string };
}

export function generateStaticParams() {
  return COURSES.map((c) => ({ courseId: c.id }));
}

export function generateMetadata({ params }: Props): Metadata {
  const course = getCourseById(params.courseId);
  if (!course) return {};
  return { title: `${course.label} Course` };
}

export default function CoursePage({ params }: Props) {
  const course = getCourseById(params.courseId);
  if (!course) notFound();

  // Load chapters for both locales for client-side switching
  const chaptersEn = getChaptersForCourse(params.courseId, 'en');
  const chaptersRu = getChaptersForCourse(params.courseId, 'ru');

  // Use RU as primary (it has more content), fall back to EN
  const chapters = chaptersRu.length > 0 ? chaptersRu : chaptersEn;

  return (
    <CourseChaptersView
      course={course}
      courseId={params.courseId}
      chapters={chapters}
      chaptersEn={chaptersEn}
      chaptersRu={chaptersRu}
    />
  );
}
