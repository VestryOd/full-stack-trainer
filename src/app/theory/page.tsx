import { TOPICS } from '@/constants/topics';
import { getTopicArticleCount } from '@/lib/content';
import { TheoryTopicsGrid } from '@/components/theory/TheoryTopicsGrid';

export default function TheoryPage() {
  const topicsWithCounts = TOPICS.map((t) => ({
    ...t,
    articleCount: getTopicArticleCount(t.id),
  }));

  const available = topicsWithCounts.filter((t) => t.articleCount > 0);
  const upcoming  = topicsWithCounts.filter((t) => t.articleCount === 0);

  return (
    <div className="container py-8">
      <TheoryTopicsGrid available={available} upcoming={upcoming} />
    </div>
  );
}
