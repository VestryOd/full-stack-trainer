import { notFound } from 'next/navigation';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getArticle, getSlugsForTopic } from '@/lib/content';
import { renderArticleHtml } from '@/components/theory/ArticleRenderer';
import { ArticleView } from '@/components/theory/ArticleView';

interface Props {
  params: { topicId: string; slug: string };
}

export async function generateStaticParams() {
  const params: { topicId: string; slug: string }[] = [];
  for (const topic of TOPICS) {
    const slugsRu = getSlugsForTopic(topic.id, 'ru');
    const slugsEn = getSlugsForTopic(topic.id, 'en');
    const seen = new Set<string>();
    const allSlugs = [...slugsRu, ...slugsEn].filter((s) => {
      if (seen.has(s)) return false;
      seen.add(s);
      return true;
    });
    for (const slug of allSlugs) {
      params.push({ topicId: topic.id, slug });
    }
  }
  return params;
}

export default async function ArticlePage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const articleRu = getArticle(params.topicId, params.slug, 'ru');
  const articleEn = getArticle(params.topicId, params.slug, 'en');
  if (!articleRu && !articleEn) notFound();

  // Pre-render both locales on the server
  const [htmlEn, htmlRu] = await Promise.all([
    articleEn ? renderArticleHtml(articleEn.content) : Promise.resolve(null),
    articleRu ? renderArticleHtml(articleRu.content) : Promise.resolve(null),
  ]);

  // Navigation slugs
  const slugsRu = getSlugsForTopic(params.topicId, 'ru');
  const slugsEn = getSlugsForTopic(params.topicId, 'en');
  const slugs = slugsRu.length > 0 ? slugsRu : slugsEn;

  const idx = slugs.indexOf(params.slug);
  const prevSlug = idx > 0 ? slugs[idx - 1] : null;
  const nextSlug = idx < slugs.length - 1 ? slugs[idx + 1] : null;

  return (
    <ArticleView
      topicId={params.topicId}
      topicLabel={topic.label}
      slug={params.slug}
      htmlEn={htmlEn}
      htmlRu={htmlRu}
      prevSlug={prevSlug}
      nextSlug={nextSlug}
    />
  );
}
