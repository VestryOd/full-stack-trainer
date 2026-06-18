'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';

interface QuizTopicsGridProps {
  topics: Topic[];
  questionCounts: Record<string, number>;
}

const PRESETS = [10, 20, 30] as const;

export function QuizTopicsGrid({ topics, questionCounts }: QuizTopicsGridProps) {
  const { t2 } = useLocale();
  const router = useRouter();
  const [activeTopic, setActiveTopic] = useState<Topic | null>(null);
  const [customCount, setCustomCount] = useState('');

  const total = activeTopic ? (questionCounts[activeTopic.id] ?? 0) : 0;

  function openSheet(topic: Topic) {
    setActiveTopic(topic);
    setCustomCount('');
  }

  function closeSheet() {
    setActiveTopic(null);
    setCustomCount('');
  }

  function startQuiz(count: number) {
    if (!activeTopic) return;
    const safeCount = Math.min(count, total);
    closeSheet();
    router.push(`/quiz/${activeTopic.id}-${safeCount}`);
  }

  function handleCustomStart() {
    const n = parseInt(customCount, 10);
    if (isNaN(n) || n < 1 || n > total) return;
    startQuiz(n);
  }

  const customValue = parseInt(customCount, 10);
  const customValid = !isNaN(customValue) && customValue >= 1 && customValue <= total;

  return (
    <>
      <div className="container py-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t2('quiz.title')}</h1>
          <p className="text-muted-foreground mt-1">{t2('quiz.subtitle')}</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {topics.map((topic) => (
            <Card
              key={topic.id}
              className="cursor-pointer hover:border-primary transition-colors"
              onClick={() => openSheet(topic)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{topic.label}</CardTitle>
                  <Badge variant="secondary" className="shrink-0 tabular-nums">
                    {questionCounts[topic.id] ?? 0}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{t2('quiz.clickToStart')}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <Sheet open={activeTopic !== null} onOpenChange={(open) => !open && closeSheet()}>
        <SheetContent side="right" className="flex flex-col gap-6">
          <SheetHeader>
            <SheetTitle>{activeTopic?.label}</SheetTitle>
            <SheetDescription>
              {total} {t2('quiz.questionsAvailable')}
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-3">
            <p className="text-sm font-medium">{t2('quiz.selectCount')}</p>
            <div className="flex gap-2 flex-wrap">
              {PRESETS.filter((n) => n <= total).map((n) => (
                <Button key={n} variant="outline" onClick={() => startQuiz(n)}>
                  {n}
                </Button>
              ))}
              <Button variant="default" onClick={() => startQuiz(total)}>
                {t2('quiz.all')} ({total})
              </Button>
            </div>
          </div>

          <Separator />

          <div className="space-y-3">
            <p className="text-sm font-medium">{t2('quiz.customCount')}</p>
            <div className="flex gap-2">
              <Input
                type="number"
                min={1}
                max={total}
                placeholder={`1–${total}`}
                value={customCount}
                onChange={(e) => setCustomCount(e.target.value)}
                className="w-28"
              />
              <Button onClick={handleCustomStart} disabled={!customValid}>
                {t2('quiz.startBtn')}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
