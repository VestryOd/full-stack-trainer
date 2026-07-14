'use client';

import Link from 'next/link';
import type { Course, CourseChapter } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { CourseChapterList } from './CourseChapterList';
import { ChevronRight } from 'lucide-react';

interface CourseChaptersViewProps {
  course: Course;
  courseId: string;
  chapters: CourseChapter[];
  chaptersEn: CourseChapter[];
  chaptersRu: CourseChapter[];
}

export function CourseChaptersView({ course, courseId, chapters, chaptersEn, chaptersRu }: CourseChaptersViewProps) {
  const { t2 } = useLocale();

  return (
    <div className="container py-8 max-w-3xl space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
        <Link href="/courses" className="hover:text-foreground transition-colors">{t2('courses.title')}</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">{course.label}</span>
      </nav>

      <div>
        <h1 className="text-2xl font-mono font-semibold">{course.label}</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {chapters.length > 0 ? `${chapters.length} ${t2('courses.chapters')}` : t2('courses.noChaptersYet')}
        </p>
      </div>

      {chapters.length > 0 ? (
        <CourseChapterList
          courseId={courseId}
          slugs={chapters.map((c) => c.slug)}
          chaptersEn={chaptersEn}
          chaptersRu={chaptersRu}
        />
      ) : (
        <p className="text-muted-foreground text-center py-12 text-sm">
          {t2('courses.comingSoonCourse')}
        </p>
      )}
    </div>
  );
}
