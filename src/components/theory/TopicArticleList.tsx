'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { useLocale } from '@/context/LocaleContext';
import type { TheoryArticle } from '@/types';
import { cn } from '@/lib/utils';
import { FileText, Clock } from 'lucide-react';

interface TopicArticleListProps {
  topicId: string;
  slugs: string[];
  articlesEn: TheoryArticle[];
  articlesRu: TheoryArticle[];
}

function estimateReadTime(content: string): number {
  const words = content.split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}

function extractTitle(content: string, slug: string): string {
  const match = content.match(/^(?:<!--.*?-->\s*)?#\s+(.+)$/m);
  return match ? match[1].trim() : slug.replace(/^\d+-/, '').replace(/-/g, ' ');
}

export function TopicArticleList({ topicId, articlesEn, articlesRu }: TopicArticleListProps) {
  const { locale: globalLocale } = useLocale();
  const [locale, setLocale] = useState(globalLocale);

  useEffect(() => { setLocale(globalLocale); }, [globalLocale]);

  const articles = locale === 'ru' && articlesRu.length > 0 ? articlesRu : articlesEn;
  const hasLocale = (l: 'en' | 'ru') => (l === 'en' ? articlesEn.length > 0 : articlesRu.length > 0);

  return (
    <div className="space-y-3">
      {/* Language toggle */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground font-mono">{articles.length} articles</p>
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

      {articles.map((article, idx) => {
        const title = extractTitle(article.content, article.slug);
        const readTime = estimateReadTime(article.content);
        return (
          <Link
            key={article.slug}
            href={`/theory/${topicId}/${article.slug}`}
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
              {readTime} min
            </span>
          </Link>
        );
      })}
    </div>
  );
}
