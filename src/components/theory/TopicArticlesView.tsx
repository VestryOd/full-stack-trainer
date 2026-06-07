'use client';

import Link from 'next/link';
import type { TheoryArticle, Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { TopicArticleList } from './TopicArticleList';
import { ChevronRight } from 'lucide-react';

interface TopicArticlesViewProps {
  topic: Topic;
  topicId: string;
  articles: TheoryArticle[];
  articlesEn: TheoryArticle[];
  articlesRu: TheoryArticle[];
}

export function TopicArticlesView({ topic, topicId, articles, articlesEn, articlesRu }: TopicArticlesViewProps) {
  const { t2 } = useLocale();

  return (
    <div className="container py-8 max-w-3xl space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
        <Link href="/theory" className="hover:text-foreground transition-colors">{t2('theory.title')}</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">{topic.label}</span>
      </nav>

      <div>
        <h1 className="text-2xl font-mono font-semibold">{topic.label}</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {articles.length > 0 ? `${articles.length} ${t2('theory.articles')}` : t2('theory.noArticlesYet')}
        </p>
      </div>

      {articles.length > 0 ? (
        <TopicArticleList
          topicId={topicId}
          slugs={articles.map((a) => a.slug)}
          articlesEn={articlesEn}
          articlesRu={articlesRu}
        />
      ) : (
        <p className="text-muted-foreground text-center py-12 text-sm">
          {t2('theory.comingSoonTopic')}
        </p>
      )}
    </div>
  );
}
