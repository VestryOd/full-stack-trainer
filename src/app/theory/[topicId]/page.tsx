import { notFound } from 'next/navigation';
import Link from 'next/link';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getArticlesForTopic } from '@/lib/content';
import { TopicArticleList } from '@/components/theory/TopicArticleList';
import { ChevronRight } from 'lucide-react';

interface Props {
  params: { topicId: string };
}

export function generateStaticParams() {
  return TOPICS.map((t) => ({ topicId: t.id }));
}

export default function TopicPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  // Load articles for both locales for client-side switching
  const articlesEn = getArticlesForTopic(params.topicId, 'en');
  const articlesRu = getArticlesForTopic(params.topicId, 'ru');

  // Use RU as primary (it has more content), fall back to EN
  const articles = articlesRu.length > 0 ? articlesRu : articlesEn;

  return (
    <div className="container py-8 max-w-3xl space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
        <Link href="/theory" className="hover:text-foreground transition-colors">Theory</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">{topic.label}</span>
      </nav>

      <div>
        <h1 className="text-2xl font-mono font-semibold">{topic.label}</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {articles.length > 0 ? `${articles.length} articles` : 'No articles yet'}
        </p>
      </div>

      {articles.length > 0 ? (
        <TopicArticleList
          topicId={params.topicId}
          slugs={articles.map((a) => a.slug)}
          articlesEn={articlesEn}
          articlesRu={articlesRu}
        />
      ) : (
        <p className="text-muted-foreground text-center py-12 text-sm">
          Content for this topic is coming soon.
        </p>
      )}
    </div>
  );
}
