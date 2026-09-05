'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Shuffle } from 'lucide-react';
import type { Task, Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { Button } from '@/components/ui/button';
import { TaskCard } from './TaskCard';

interface TopicTasksViewProps {
  topic: Topic;
  tasks: Task[];
}

export function TopicTasksView({ topic, tasks }: TopicTasksViewProps) {
  const { locale, t2 } = useLocale();
  const router = useRouter();

  // The tasks of this topic are already here, so picking one needs no index and no
  // intermediate route — unlike «random from any topic», which lives at /tasks/random/one.
  function openRandom() {
    if (tasks.length === 0) return;
    const task = tasks[Math.floor(Math.random() * tasks.length)];
    router.push(`/tasks/${task.topicId}/${task.id}`);
  }

  return (
    <div className="container py-8 space-y-6">
      <div>
        <Link href="/tasks" className="text-sm text-muted-foreground hover:underline">
          {t2('tasks.backToTasks')}
        </Link>
        <div className="mt-2 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{topic.label}</h1>
            <p className="text-muted-foreground">{tasks.length} {t2('tasks.tasksCount')}</p>
          </div>
          {tasks.length > 0 && (
            <Button variant="outline" onClick={openRandom} className="shrink-0 gap-2">
              <Shuffle className="h-4 w-4" />
              {t2('tasks.randomOne')}
            </Button>
          )}
        </div>
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
