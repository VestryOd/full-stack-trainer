import Link from 'next/link';
import { TOPICS } from '@/constants/topics';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const LEVEL_COLORS = {
  deep:   'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  medium: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  light:  'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
};

export default function QuestionsPage() {
  return (
    <div className="container py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Questions</h1>
        <p className="text-muted-foreground mt-1">Interview questions by topic</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {TOPICS.map((topic) => (
          <Link key={topic.id} href={`/questions/${topic.id}`}>
            <Card className="h-full transition-colors hover:bg-accent cursor-pointer">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{topic.label}</CardTitle>
                  <Badge variant="outline" className={LEVEL_COLORS[topic.level]}>
                    {topic.level}
                  </Badge>
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
