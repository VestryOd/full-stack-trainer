import { notFound } from 'next/navigation';
import Link from 'next/link';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getArticle, getSlugsForTopic } from '@/lib/content';
import { ArticleRenderer } from '@/components/theory/ArticleRenderer';

interface Props {
  params: { topicId: string; slug: string };
}

export async function generateStaticParams() {
  const params: { topicId: string; slug: string }[] = [];
  for (const topic of TOPICS) {
    const slugs = getSlugsForTopic(topic.id, 'ru');
    for (const slug of slugs) {
      params.push({ topicId: topic.id, slug });
    }
  }
  return params;
}

export default async function ArticlePage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const article = getArticle(params.topicId, params.slug, 'ru');
  if (!article) notFound();

  return (
    <div className="container py-8 max-w-4xl">
      <div className="mb-6 space-y-1">
        <div className="flex gap-2 text-sm text-muted-foreground">
          <Link href="/theory" className="hover:underline">Theory</Link>
          <span>/</span>
          <Link href={`/theory/${topic.id}`} className="hover:underline">{topic.label}</Link>
        </div>
        <h1 className="text-3xl font-bold">{article.title}</h1>
      </div>
      <ArticleRenderer content={article.content} />
    </div>
  );
}
