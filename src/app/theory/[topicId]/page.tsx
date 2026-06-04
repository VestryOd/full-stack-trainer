import { notFound } from 'next/navigation';
import Link from 'next/link';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getArticlesForTopic } from '@/lib/content';
import { ArticleCard } from '@/components/theory/ArticleCard';

interface Props {
  params: { topicId: string };
}

export function generateStaticParams() {
  return TOPICS.map((t) => ({ topicId: t.id }));
}

export default function TopicPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const articles = getArticlesForTopic(params.topicId, 'ru');

  return (
    <div className="container py-8 space-y-6">
      <div>
        <Link href="/theory" className="text-sm text-muted-foreground hover:underline">
          ← Theory
        </Link>
        <h1 className="text-3xl font-bold mt-2">{topic.label}</h1>
        <p className="text-muted-foreground">
          {articles.length > 0 ? `${articles.length} articles` : 'No articles yet'}
        </p>
      </div>
      {articles.length > 0 ? (
        <div className="flex flex-col gap-3">
          {articles.map((article) => (
            <ArticleCard key={article.slug} article={article} />
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground text-center py-12">
          Content for this topic is coming soon.
        </p>
      )}
    </div>
  );
}
