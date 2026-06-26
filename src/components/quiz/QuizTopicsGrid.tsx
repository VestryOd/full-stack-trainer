'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Shuffle } from 'lucide-react';
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
const RANDOM_QUIZ_KEY = 'fst-quiz-random';

export function QuizTopicsGrid({ topics, questionCounts }: QuizTopicsGridProps) {
  const { t2 } = useLocale();
  const router = useRouter();

  // ── Single-topic sheet ────────────────────────────────────────────────────
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

  // ── Random quiz sheet ─────────────────────────────────────────────────────
  const [randomSheetOpen, setRandomSheetOpen] = useState(false);
  const [selectedTopics, setSelectedTopics] = useState<Set<string>>(
    () => new Set(topics.map((t) => t.id)),
  );
  const [randomPreset, setRandomPreset] = useState<number | 'all'>('all');

  const randomTotal = useMemo(
    () =>
      topics
        .filter((t) => selectedTopics.has(t.id))
        .reduce((sum, t) => sum + (questionCounts[t.id] ?? 0), 0),
    [topics, selectedTopics, questionCounts],
  );

  function toggleTopic(id: string) {
    setSelectedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function startRandomQuiz() {
    if (selectedTopics.size === 0) return;
    const topicIds = topics.filter((t) => selectedTopics.has(t.id)).map((t) => t.id);
    const count = randomPreset === 'all' ? randomTotal : Math.min(randomPreset, randomTotal);
    sessionStorage.setItem(RANDOM_QUIZ_KEY, JSON.stringify({ topicIds, count }));
    setRandomSheetOpen(false);
    router.push('/quiz/random');
  }

  return (
    <>
      <div className="container py-8 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{t2('quiz.title')}</h1>
          <p className="text-muted-foreground mt-1">{t2('quiz.subtitle')}</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Random Quiz card — visually distinct, always first */}
          <Card
            className="cursor-pointer border-primary/40 bg-primary/5 hover:bg-primary/10 hover:border-primary transition-colors"
            onClick={() => setRandomSheetOpen(true)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Shuffle className="h-4 w-4 text-primary shrink-0" />
                  {t2('quiz.randomTitle')}
                </CardTitle>
                <Badge variant="outline" className="shrink-0 text-xs border-primary/30 text-primary">
                  {topics.reduce((s, t) => s + (questionCounts[t.id] ?? 0), 0)}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{t2('quiz.randomSubtitle')}</p>
            </CardContent>
          </Card>

          {/* Per-topic cards */}
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

      {/* Single-topic config sheet */}
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

      {/* Random quiz config sheet */}
      <Sheet open={randomSheetOpen} onOpenChange={(open) => !open && setRandomSheetOpen(false)}>
        <SheetContent side="right" className="flex flex-col gap-5 overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Shuffle className="h-4 w-4 text-primary" />
              {t2('quiz.randomTitle')}
            </SheetTitle>
            <SheetDescription>
              {randomTotal} {t2('quiz.questionsAvailable')}
            </SheetDescription>
          </SheetHeader>

          {/* Topic checklist */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">{t2('quiz.randomTopics')}</p>
              <div className="flex gap-3 text-xs">
                <button
                  onClick={() => setSelectedTopics(new Set(topics.map((t) => t.id)))}
                  className="text-primary hover:underline"
                >
                  {t2('quiz.randomSelectAll')}
                </button>
                <button
                  onClick={() => setSelectedTopics(new Set())}
                  className="text-muted-foreground hover:underline"
                >
                  {t2('quiz.randomDeselectAll')}
                </button>
              </div>
            </div>
            <div className="space-y-0.5 max-h-52 overflow-y-auto border border-border rounded-md p-1">
              {topics.map((topic) => (
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
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {questionCounts[topic.id] ?? 0}
                  </span>
                </label>
              ))}
            </div>
          </div>

          <Separator />

          {/* Count selector */}
          <div className="space-y-3">
            <p className="text-sm font-medium">{t2('quiz.selectCount')}</p>
            <div className="flex gap-2 flex-wrap">
              {PRESETS.filter((n) => n <= randomTotal).map((n) => (
                <Button
                  key={n}
                  variant={randomPreset === n ? 'default' : 'outline'}
                  onClick={() => setRandomPreset(n)}
                >
                  {n}
                </Button>
              ))}
              <Button
                variant={randomPreset === 'all' ? 'default' : 'outline'}
                onClick={() => setRandomPreset('all')}
                disabled={randomTotal === 0}
              >
                {t2('quiz.all')} ({randomTotal})
              </Button>
            </div>
          </div>

          <Button
            size="lg"
            className="mt-auto"
            disabled={selectedTopics.size === 0 || randomTotal === 0}
            onClick={startRandomQuiz}
          >
            {t2('quiz.startBtn')}
          </Button>
        </SheetContent>
      </Sheet>
    </>
  );
}
