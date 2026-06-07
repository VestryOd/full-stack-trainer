'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { useLocale } from '@/context/LocaleContext';
import { ArticleContent } from './ArticleContent';
import { cn } from '@/lib/utils';
import { ChevronRight, ChevronLeft } from 'lucide-react';

interface ArticleViewProps {
  topicId: string;
  topicLabel: string;
  slug: string;
  htmlEn: string | null;
  htmlRu: string | null;
  prevSlug: string | null;
  nextSlug: string | null;
}

function slugToLabel(slug: string): string {
  return slug.replace(/^\d+-/, '').replace(/-/g, ' ');
}

function extractTitleFromHtml(html: string): string {
  const match = html.match(/<h1[^>]*>(.*?)<\/h1>/i);
  if (!match) return '';
  // Strip any HTML tags from the title
  return match[1].replace(/<[^>]+>/g, '').trim();
}

export function ArticleView({
  topicId,
  topicLabel,
  slug,
  htmlEn,
  htmlRu,
  prevSlug,
  nextSlug,
}: ArticleViewProps) {
  const { locale: globalLocale } = useLocale();
  const [locale, setLocale] = useState<'en' | 'ru'>(globalLocale);

  useEffect(() => { setLocale(globalLocale); }, [globalLocale]);

  const hasEn = !!htmlEn;
  const hasRu = !!htmlRu;

  const effectiveLocale = locale === 'ru' && hasRu ? 'ru' : locale === 'en' && hasEn ? 'en' : hasRu ? 'ru' : 'en';
  const html = effectiveLocale === 'ru' ? htmlRu! : htmlEn!;
  const title = extractTitleFromHtml(html);

  return (
    <div className="container py-8 max-w-4xl">
      {/* Breadcrumb + locale toggle */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <nav className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono min-w-0">
          <Link href="/theory" className="hover:text-foreground transition-colors whitespace-nowrap">Theory</Link>
          <ChevronRight className="h-3 w-3 flex-shrink-0" />
          <Link href={`/theory/${topicId}`} className="hover:text-foreground transition-colors whitespace-nowrap">{topicLabel}</Link>
          <ChevronRight className="h-3 w-3 flex-shrink-0" />
          <span className="text-foreground truncate">{title || slugToLabel(slug)}</span>
        </nav>

        {/* Language toggle */}
        <div className="flex rounded border border-border overflow-hidden text-xs font-mono flex-shrink-0">
          {(['en', 'ru'] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLocale(l)}
              disabled={l === 'en' ? !hasEn : !hasRu}
              className={cn(
                'px-2 py-0.5 transition-colors uppercase disabled:opacity-30 disabled:cursor-not-allowed',
                effectiveLocale === l
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Article content */}
      <article className="animate-fade-in" key={effectiveLocale}>
        <ArticleContent html={html} />
      </article>

      {/* Prev / Next navigation */}
      {(prevSlug || nextSlug) && (
        <nav className="mt-12 pt-6 border-t border-border flex items-center justify-between gap-4">
          {prevSlug ? (
            <Link
              href={`/theory/${topicId}/${prevSlug}`}
              className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors max-w-xs"
            >
              <ChevronLeft className="h-4 w-4 flex-shrink-0 group-hover:-translate-x-0.5 transition-transform" />
              <span className="truncate">{slugToLabel(prevSlug)}</span>
            </Link>
          ) : (
            <div />
          )}
          {nextSlug ? (
            <Link
              href={`/theory/${topicId}/${nextSlug}`}
              className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors max-w-xs text-right"
            >
              <span className="truncate">{slugToLabel(nextSlug)}</span>
              <ChevronRight className="h-4 w-4 flex-shrink-0 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          ) : (
            <div />
          )}
        </nav>
      )}
    </div>
  );
}
