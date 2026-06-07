'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { useLocale } from '@/context/LocaleContext';
import { SolutionSpoiler } from './SolutionSpoiler';
import { Badge } from '@/components/ui/badge';
import type { Task, Topic } from '@/types';

interface TaskViewProps {
  topic: Topic;
  task: Task;
  descriptionHtml: { en: string; ru: string };
  solutionExplanationHtml: { en: string; ru: string };
  /** Rendered server-side (CodeBlock is an async server component) and passed down. */
  starterCodeBlock: ReactNode;
  solutionCodeBlock: ReactNode;
}

const DIFFICULTY_COLORS = {
  easy:   'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  hard:   'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

export function TaskView({
  topic,
  task,
  descriptionHtml,
  solutionExplanationHtml,
  starterCodeBlock,
  solutionCodeBlock,
}: TaskViewProps) {
  const { t } = useLocale();

  return (
    <div className="container py-8 max-w-4xl space-y-6">
      <div>
        <div className="flex gap-2 text-sm text-muted-foreground">
          <Link href="/tasks" className="hover:underline">Tasks</Link>
          <span>/</span>
          <Link href={`/tasks/${topic.id}`} className="hover:underline">{topic.label}</Link>
        </div>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-3xl font-bold">{t(task.title)}</h1>
          <Badge variant="outline" className={DIFFICULTY_COLORS[task.difficulty]}>
            {task.difficulty}
          </Badge>
        </div>
      </div>

      <div className="article-body" dangerouslySetInnerHTML={{ __html: t(descriptionHtml) }} />

      {task.starterCode && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Starter Code</h2>
          {starterCodeBlock}
        </div>
      )}

      <SolutionSpoiler>
        <div className="space-y-4">
          {solutionCodeBlock}
          <div className="article-body text-sm" dangerouslySetInnerHTML={{ __html: t(solutionExplanationHtml) }} />
        </div>
      </SolutionSpoiler>

      <div className="flex flex-wrap gap-1">
        {task.tags.map((tag) => (
          <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
        ))}
      </div>
    </div>
  );
}
