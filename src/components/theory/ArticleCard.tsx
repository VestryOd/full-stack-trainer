import Link from 'next/link';
import type { TheoryArticle } from '@/types';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';

interface ArticleCardProps {
  article: TheoryArticle;
}

export function ArticleCard({ article }: ArticleCardProps) {
  return (
    <Link href={`/theory/${article.topicId}/${article.slug}`}>
      <Card className="transition-colors hover:bg-accent cursor-pointer">
        <CardHeader>
          <CardTitle className="text-base">{article.title}</CardTitle>
        </CardHeader>
      </Card>
    </Link>
  );
}
