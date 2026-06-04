import Link from 'next/link';
import { TOPICS } from '@/constants/topics';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function QuizPage() {
  return (
    <div className="container py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Quiz</h1>
        <p className="text-muted-foreground mt-1">Test your knowledge with multiple-choice questions</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {TOPICS.map((topic) => (
          <Card key={topic.id}>
            <CardHeader>
              <CardTitle className="text-base">{topic.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <Button asChild size="sm" className="w-full">
                <Link href={`/quiz/${topic.id}-10`}>Start Quiz (10 questions)</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
