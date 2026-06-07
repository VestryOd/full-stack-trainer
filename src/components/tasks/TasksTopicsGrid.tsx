'use client';

import Link from 'next/link';
import type { Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface TopicWithCount extends Topic {
  count: number;
}

interface TasksTopicsGridProps {
  topicsWithTasks: TopicWithCount[];
  totalTasks: number;
}

export function TasksTopicsGrid({ topicsWithTasks, totalTasks }: TasksTopicsGridProps) {
  const { t2 } = useLocale();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">{t2('tasks.title')}</h1>
        <p className="text-muted-foreground mt-1">
          {t2('tasks.subtitle')} {totalTasks} {t2('tasks.tasksWord')} {topicsWithTasks.length} {t2('tasks.topicsWord')}
        </p>
      </div>
      {topicsWithTasks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {topicsWithTasks.map((topic) => (
            <Link key={topic.id} href={`/tasks/${topic.id}`}>
              <Card className="h-full transition-colors hover:bg-accent cursor-pointer">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{topic.label}</CardTitle>
                    <Badge variant="secondary">{topic.count}</Badge>
                  </div>
                  <CardDescription>{topic.count} {t2('tasks.tasksCount')}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-center text-muted-foreground py-12">
          No tasks yet. Add content via Prompt 2.
        </p>
      )}
    </div>
  );
}
