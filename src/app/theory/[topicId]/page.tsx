import { notFound } from 'next/navigation';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getArticlesForTopic } from '@/lib/content';
import { TopicArticlesView } from '@/components/theory/TopicArticlesView';

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
    <TopicArticlesView
      topic={topic}
      topicId={params.topicId}
      articles={articles}
      articlesEn={articlesEn}
      articlesRu={articlesRu}
    />
  );
}
