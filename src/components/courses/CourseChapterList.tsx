'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { useLocale } from '@/context/LocaleContext';
import type { CourseChapter } from '@/types';
import { cn } from '@/lib/utils';
import { FileText, Clock } from 'lucide-react';

interface CourseChapterListProps {
  courseId: string;
  slugs: string[];
  chaptersEn: CourseChapter[];
  chaptersRu: CourseChapter[];
}

function estimateReadTime(content: string): number {
  const words = content.split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}

function extractTitle(content: string, slug: string): string {
  const match = content.match(/^(?:<!--.*?-->\s*)?#\s+(.+)$/m);
  return match ? match[1].trim() : slug.replace(/^\d+-/, '').replace(/-/g, ' ');
}

export function CourseChapterList({ courseId, chaptersEn, chaptersRu }: CourseChapterListProps) {
  const { locale: globalLocale, t2 } = useLocale();
  const [locale, setLocale] = useState(globalLocale);

  useEffect(() => { setLocale(globalLocale); }, [globalLocale]);

  const chapters = locale === 'ru' && chaptersRu.length > 0 ? chaptersRu : chaptersEn;
  const hasLocale = (l: 'en' | 'ru') => (l === 'en' ? chaptersEn.length > 0 : chaptersRu.length > 0);

  return (
    <div className="space-y-3">
      {/* Language toggle */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground font-mono">{chapters.length} {t2('courses.chapters')}</p>
        <div className="flex rounded border border-border overflow-hidden text-xs font-mono">
          {(['en', 'ru'] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLocale(l)}
              disabled={!hasLocale(l)}
              className={cn(
                'px-2 py-0.5 transition-colors uppercase disabled:opacity-30 disabled:cursor-not-allowed',
                locale === l
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      {chapters.map((chapter, idx) => {
        const title = extractTitle(chapter.content, chapter.slug);
        const readTime = estimateReadTime(chapter.content);
        return (
          <Link
            key={chapter.slug}
            href={`/courses/${courseId}/${chapter.slug}`}
            className="group flex items-center gap-3 p-3 bg-card border border-border rounded-md hover:border-muted-foreground/50 transition-colors"
          >
            <span className="font-mono text-xs text-muted-foreground w-5 text-right flex-shrink-0">
              {String(idx + 1).padStart(2, '0')}
            </span>
            <FileText className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
            <span className="flex-1 text-sm group-hover:text-foreground transition-colors line-clamp-1">
              {title}
            </span>
            <span className="flex items-center gap-1 text-xs text-muted-foreground flex-shrink-0">
              <Clock className="h-3 w-3" />
              {readTime} {t2('courses.minRead')}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
