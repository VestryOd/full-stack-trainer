'use client';

import Link from 'next/link';
import type { Task, Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { TaskCard } from './TaskCard';

interface TopicTasksViewProps {
  topic: Topic;
  tasks: Task[];
}

export function TopicTasksView({ topic, tasks }: TopicTasksViewProps) {
  const { locale, t2 } = useLocale();

  return (
    <div className="container py-8 space-y-6">
      <div>
        <Link href="/tasks" className="text-sm text-muted-foreground hover:underline">
          {t2('tasks.backToTasks')}
        </Link>
        <h1 className="text-3xl font-bold mt-2">{topic.label}</h1>
        <p className="text-muted-foreground">{tasks.length} {t2('tasks.tasksCount')}</p>
      </div>
      {tasks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} locale={locale} />
          ))}
        </div>
      ) : (
        <p className="text-center text-muted-foreground py-12">
          {t2('tasks.noTasksYet')}
        </p>
      )}
    </div>
  );
}
