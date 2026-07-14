'use client';

import Link from 'next/link';
import type { Course } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { cn } from '@/lib/utils';

const LEVEL_STYLES: Record<string, string> = {
  deep:   'bg-blue-500/10 text-blue-400 border-blue-500/20',
  medium: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  light:  'bg-muted text-muted-foreground border-border',
};

interface CourseWithCount extends Course {
  chapterCount: number;
}

interface CoursesGridProps {
  available: CourseWithCount[];
  upcoming: CourseWithCount[];
}

export function CoursesGrid({ available, upcoming }: CoursesGridProps) {
  const { t2 } = useLocale();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-mono font-semibold">{t2('courses.title')}</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {available.length} {t2('courses.available')} · {available.reduce((sum, c) => sum + c.chapterCount, 0)} {t2('courses.chapters')}
        </p>
      </div>

      {/* Courses with content */}
      <section className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {available.map((course) => (
            <Link
              key={course.id}
              href={`/courses/${course.id}`}
              className="group flex items-center justify-between p-4 bg-card border border-border rounded-md hover:border-muted-foreground/50 transition-colors"
            >
              <div>
                <p className="text-sm font-medium group-hover:text-foreground transition-colors">
                  {course.label}
                </p>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">
                  {course.chapterCount} {t2('courses.chapters')}
                </p>
              </div>
              <span
                className={cn(
                  'text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border flex-shrink-0',
                  LEVEL_STYLES[course.level],
                )}
              >
                {course.level}
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Upcoming courses */}
      {upcoming.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-mono text-muted-foreground uppercase tracking-wide">
            {t2('courses.comingSoon')} ({upcoming.length})
          </h2>
          <div className="flex flex-wrap gap-2">
            {upcoming.map((course) => (
              <span
                key={course.id}
                className="inline-flex items-center px-2.5 py-1 rounded border border-border text-xs text-muted-foreground font-mono opacity-50"
              >
                {course.label}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
