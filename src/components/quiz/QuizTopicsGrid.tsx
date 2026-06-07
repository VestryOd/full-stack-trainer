'use client';

import Link from 'next/link';
import type { Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface QuizTopicsGridProps {
  topics: Topic[];
}

export function QuizTopicsGrid({ topics }: QuizTopicsGridProps) {
  const { t2 } = useLocale();

  return (
    <div className="container py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">{t2('quiz.title')}</h1>
        <p className="text-muted-foreground mt-1">{t2('quiz.subtitle')}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {topics.map((topic) => (
          <Card key={topic.id}>
            <CardHeader>
              <CardTitle className="text-base">{topic.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <Button asChild size="sm" className="w-full">
                <Link href={`/quiz/${topic.id}-10`}>{t2('quiz.startBtn')} (10)</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
