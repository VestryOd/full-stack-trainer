'use client';

import { useRef, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Shuffle } from 'lucide-react';
import { useLocale } from '@/context/LocaleContext';
import { useContentHighlight } from '@/lib/search/useContentHighlight';
import { SolutionSpoiler } from './SolutionSpoiler';
import { TaskSetBar } from './TaskSetBar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { Task, Topic } from '@/types';

interface TaskViewProps {
  topic: Topic;
  task: Task;
  descriptionHtml: { en: string; ru: string };
  solutionExplanationHtml: { en: string; ru: string };
  /** Rendered server-side (CodeBlock is an async server component) and passed down. */
  starterCodeBlock: ReactNode;
  solutionCodeBlock: ReactNode;
  /** Ids of the sibling tasks in this topic, so «another one» needs no task index. */
  topicTaskIds: string[];
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
  topicTaskIds,
}: TaskViewProps) {
  const { t, t2, locale } = useLocale();
  const router = useRouter();
  const contentRef = useRef<HTMLDivElement>(null);
  useContentHighlight(contentRef, [locale]);

  const siblings = topicTaskIds.filter((id) => id !== task.id);

  function openAnotherInTopic() {
    if (siblings.length === 0) return;
    const id = siblings[Math.floor(Math.random() * siblings.length)];
    router.push(`/tasks/${topic.id}/${id}`);
  }

  return (
    <div ref={contentRef} className="container py-8 max-w-4xl space-y-6">
      <div>
        <div className="flex gap-2 text-sm text-muted-foreground">
          <Link href="/tasks" className="hover:underline">{t2('tasks.title')}</Link>
          <span>/</span>
          <Link href={`/tasks/${topic.id}`} className="hover:underline">{topic.label}</Link>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold">{t(task.title)}</h1>
          <Badge variant="outline" className={DIFFICULTY_COLORS[task.difficulty]}>
            {task.difficulty}
          </Badge>
          {siblings.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={openAnotherInTopic}
              className="gap-1.5 text-muted-foreground"
            >
              <Shuffle className="h-3.5 w-3.5" />
              {t2('tasks.another')}
            </Button>
          )}
        </div>
      </div>

      <TaskSetBar taskId={task.id} />

      <div className="article-body task-description" dangerouslySetInnerHTML={{ __html: t(descriptionHtml) }} />

      {task.starterCode && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">{t2('tasks.starterCode')}</h2>
          {starterCodeBlock}
        </div>
      )}

      <SolutionSpoiler label={t2('tasks.showSolution')} hideLabel={t2('tasks.hideSolution')} revealLabel={t2('tasks.revealSolution')}>
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

      {/* Offered at the point the task is actually finished, not only in the header */}
      <div className="border-t border-border pt-4 space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{t2('tasks.whatsNext')}</p>
        <div className="flex flex-wrap gap-2">
          {siblings.length > 0 && (
            <Button variant="outline" size="sm" onClick={openAnotherInTopic} className="gap-2">
              <Shuffle className="h-4 w-4" />
              {t2('tasks.anotherInTopic')}
            </Button>
          )}
          <Button variant="outline" size="sm" asChild className="gap-2">
            <Link href="/tasks/random/one">
              <Shuffle className="h-4 w-4" />
              {t2('tasks.anyRandom')}
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
