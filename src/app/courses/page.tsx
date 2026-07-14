import type { Metadata } from 'next';
import { COURSES } from '@/constants/courses';
import { getCourseChapterCount } from '@/lib/courses';
import { CoursesGrid } from '@/components/courses/CoursesGrid';

export const metadata: Metadata = { title: 'Courses' };

export default function CoursesPage() {
  const coursesWithCounts = COURSES.map((c) => ({
    ...c,
    chapterCount: getCourseChapterCount(c.id),
  }));

  const available = coursesWithCounts.filter((c) => c.chapterCount > 0);
  const upcoming  = coursesWithCounts.filter((c) => c.chapterCount === 0);

  return (
    <div className="container py-8">
      <CoursesGrid available={available} upcoming={upcoming} />
    </div>
  );
}
