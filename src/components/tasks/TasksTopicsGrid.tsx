'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Shuffle } from 'lucide-react';
import type { Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { buildPlaylist, savePlaylist, type TaskRef } from '@/lib/tasks-random';

interface TopicWithCount extends Topic {
  count: number;
}

interface TasksTopicsGridProps {
  topicsWithTasks: TopicWithCount[];
  totalTasks: number;
  taskIndex: TaskRef[];
}

const PRESETS = [5, 10, 20] as const;

export function TasksTopicsGrid({ topicsWithTasks, totalTasks, taskIndex }: TasksTopicsGridProps) {
  const { t2 } = useLocale();
  const router = useRouter();

  const [sheetOpen, setSheetOpen] = useState(false);
  const [selectedTopics, setSelectedTopics] = useState<Set<string>>(
    () => new Set(topicsWithTasks.map((t) => t.id)),
  );
  const [preset, setPreset] = useState<number | 'all'>(10);

  const available = useMemo(
    () =>
      topicsWithTasks
        .filter((t) => selectedTopics.has(t.id))
        .reduce((sum, t) => sum + t.count, 0),
    [topicsWithTasks, selectedTopics],
  );

  function toggleTopic(id: string) {
    setSelectedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function startSet() {
    if (selectedTopics.size === 0 || available === 0) return;
    const topicIds = topicsWithTasks.filter((t) => selectedTopics.has(t.id)).map((t) => t.id);
    const count = preset === 'all' ? available : Math.min(preset, available);
    savePlaylist(buildPlaylist(taskIndex, topicIds, count));
    setSheetOpen(false);
    router.push('/tasks/random');
  }

  return (
    <>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t2('tasks.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t2('tasks.subtitle')} {totalTasks} {t2('tasks.tasksWord')} {topicsWithTasks.length} {t2('tasks.topicsWord')}
          </p>
        </div>
        {topicsWithTasks.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Random set card — visually distinct, always first, mirrors the quiz page */}
            <Card
              className="cursor-pointer border-primary/40 bg-primary/5 hover:bg-primary/10 hover:border-primary transition-colors"
              onClick={() => setSheetOpen(true)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Shuffle className="h-4 w-4 text-primary shrink-0" />
                    {t2('tasks.randomTitle')}
                  </CardTitle>
                  <Badge variant="outline" className="shrink-0 text-xs border-primary/30 text-primary">
                    {totalTasks}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{t2('tasks.randomSubtitle')}</p>
              </CardContent>
            </Card>

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

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="right" className="flex flex-col gap-5 overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Shuffle className="h-4 w-4 text-primary" />
              {t2('tasks.randomTitle')}
            </SheetTitle>
            <SheetDescription>
              {available} {t2('tasks.tasksAvailable')}
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">{t2('tasks.randomTopics')}</p>
              <div className="flex gap-3 text-xs">
                <button
                  onClick={() => setSelectedTopics(new Set(topicsWithTasks.map((t) => t.id)))}
                  className="text-primary hover:underline"
                >
                  {t2('tasks.randomSelectAll')}
                </button>
                <button
                  onClick={() => setSelectedTopics(new Set())}
                  className="text-muted-foreground hover:underline"
                >
                  {t2('tasks.randomDeselectAll')}
                </button>
              </div>
            </div>
            <div className="space-y-0.5 max-h-52 overflow-y-auto border border-border rounded-md p-1">
              {topicsWithTasks.map((topic) => (
                <label
                  key={topic.id}
                  className="flex items-center gap-2 text-sm cursor-pointer select-none px-2 py-1.5 rounded hover:bg-muted/50"
                >
                  <input
                    type="checkbox"
                    checked={selectedTopics.has(topic.id)}
                    onChange={() => toggleTopic(topic.id)}
                    className="h-3.5 w-3.5 rounded"
                  />
                  <span className="flex-1 truncate">{topic.label}</span>
                  <span className="text-xs text-muted-foreground tabular-nums">{topic.count}</span>
                </label>
              ))}
            </div>
          </div>

          <Separator />

          <div className="space-y-3">
            <p className="text-sm font-medium">{t2('tasks.selectCount')}</p>
            <div className="flex gap-2 flex-wrap">
              {PRESETS.filter((n) => n <= available).map((n) => (
                <Button
                  key={n}
                  variant={preset === n ? 'default' : 'outline'}
                  onClick={() => setPreset(n)}
                >
                  {n}
                </Button>
              ))}
              <Button
                variant={preset === 'all' ? 'default' : 'outline'}
                onClick={() => setPreset('all')}
                disabled={available === 0}
              >
                {t2('tasks.all')} ({available})
              </Button>
            </div>
          </div>

          <Button
            size="lg"
            className="mt-auto"
            disabled={selectedTopics.size === 0 || available === 0}
            onClick={startSet}
          >
            {t2('tasks.startBtn')}
          </Button>
        </SheetContent>
      </Sheet>
    </>
  );
}
