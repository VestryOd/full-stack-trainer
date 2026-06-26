'use client';

import { useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDown, ChevronRight, Clock } from 'lucide-react';
import type { Question, Task } from '@/types';
import {
  TIMING,
  TASK_TIME_RATIOS,
  TASK_MAX_COUNTS,
  QUESTION_BANDS,
  DURATION_PRESETS,
  buildInterviewPlan,
  type DurationPreset,
} from '@/lib/interview';
import { useLocale } from '@/context/LocaleContext';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getTopicById } from '@/constants/topics';

interface InterviewConfigProps {
  allQuestions: Question[];
  allTasks: Task[];
}

function getTopicLabel(topicId: string): string {
  return getTopicById(topicId)?.label ?? topicId;
}

export function InterviewConfig({ allQuestions, allTasks }: InterviewConfigProps) {
  const { t2 } = useLocale();
  const router = useRouter();

  const [duration, setDuration] = useState<DurationPreset>(90);
  const [scope, setScope] = useState<'full' | 'custom'>('full');
  const [questionTopicsOpen, setQuestionTopicsOpen] = useState(false);
  const [taskTopicsOpen, setTaskTopicsOpen] = useState(false);

  const allQuestionTopicIds = useMemo(
    () => [...new Set(allQuestions.map((q) => q.topicId))].sort(),
    [allQuestions],
  );
  const allTaskTopicIds = useMemo(
    () => [...new Set(allTasks.map((t) => t.topicId))].sort(),
    [allTasks],
  );

  const [selectedQuestionTopics, setSelectedQuestionTopics] = useState<Set<string>>(
    () => new Set(allQuestionTopicIds),
  );
  const [selectedTaskTopics, setSelectedTaskTopics] = useState<Set<string>>(
    () => new Set(allTaskTopicIds),
  );

  const toggleQuestionTopic = useCallback((id: string) => {
    setSelectedQuestionTopics((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleTaskTopic = useCallback((id: string) => {
    setSelectedTaskTopics((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Live estimate (no shuffle — uses counts and band shares)
  const estimate = useMemo(() => {
    const activeQuestions =
      scope === 'custom'
        ? allQuestions.filter((q) => selectedQuestionTopics.has(q.topicId))
        : allQuestions;
    const activeTasks =
      scope === 'custom'
        ? allTasks.filter((t) => selectedTaskTopics.has(t.topicId))
        : allTasks;

    const taskBudget = Math.round(duration * TASK_TIME_RATIOS[duration]);
    const maxTasks = TASK_MAX_COUNTS[duration];

    let estTaskMinutes = 0;
    let taskCount = 0;
    for (const diff of ['easy', 'medium', 'hard'] as const) {
      if (taskCount >= maxTasks) break;
      const available = activeTasks.filter((t) => t.difficulty === diff);
      let i = 0;
      while (i < available.length && taskCount < maxTasks) {
        const mins = TIMING.taskMinutes[diff];
        if (estTaskMinutes + mins > taskBudget) break;
        estTaskMinutes += mins;
        taskCount++;
        i++;
      }
    }

    const questionBudget = duration - estTaskMinutes;
    let questionCount = 0;
    let estQuestionMinutes = 0;
    for (const band of QUESTION_BANDS) {
      const bandBudget = questionBudget * band.share;
      const avgMin = TIMING.questionMinutes[band.difficulty];
      const available = activeQuestions.filter((q) => q.difficulty === band.difficulty).length;
      const count = Math.min(Math.floor(bandBudget / avgMin), available);
      questionCount += count;
      estQuestionMinutes += count * avgMin;
    }

    return {
      taskCount,
      questionCount,
      estimatedMinutes: Math.round(estTaskMinutes + estQuestionMinutes),
    };
  }, [duration, scope, selectedQuestionTopics, selectedTaskTopics, allQuestions, allTasks]);

  function handleStart() {
    const plan = buildInterviewPlan(
      duration,
      {
        scope,
        questionTopicIds: scope === 'custom' ? [...selectedQuestionTopics] : undefined,
        taskTopicIds: scope === 'custom' ? [...selectedTaskTopics] : undefined,
      },
      allQuestions,
      allTasks,
    );
    sessionStorage.setItem('fst-interview-plan', JSON.stringify(plan));
    router.push('/interview/session');
  }

  return (
    <div className="container py-8 max-w-2xl space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <Clock className="h-6 w-6 text-primary" />
          <h1 className="text-3xl font-bold">{t2('interview.title')}</h1>
        </div>
        <p className="text-muted-foreground">{t2('interview.subtitle')}</p>
      </div>

      {/* Duration selector */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {t2('interview.duration')}
        </h2>
        <div className="flex gap-3">
          {DURATION_PRESETS.map((preset) => (
            <button
              key={preset}
              onClick={() => setDuration(preset)}
              className={cn(
                'flex-1 border rounded-lg py-4 text-center transition-colors',
                duration === preset
                  ? 'border-primary bg-primary text-primary-foreground font-semibold'
                  : 'border-border hover:border-primary/50 text-foreground',
              )}
            >
              <span className="text-2xl font-bold block">{preset}</span>
              <span className="text-xs">{t2('interview.min')}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Scope selector */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {t2('interview.scope')}
        </h2>
        <div className="flex gap-3">
          <button
            onClick={() => setScope('full')}
            className={cn(
              'flex-1 border rounded-lg p-4 text-left transition-colors',
              scope === 'full'
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50',
            )}
          >
            <p className="font-medium text-sm">{t2('interview.fullInterview')}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{t2('interview.fullInterviewDesc')}</p>
          </button>
          <button
            onClick={() => setScope('custom')}
            className={cn(
              'flex-1 border rounded-lg p-4 text-left transition-colors',
              scope === 'custom'
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50',
            )}
          >
            <p className="font-medium text-sm">{t2('interview.custom')}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{t2('interview.customDesc')}</p>
          </button>
        </div>

        {/* Custom checklists */}
        {scope === 'custom' && (
          <div className="space-y-3 mt-2">
            {/* Question topics */}
            <div className="border border-border rounded-md overflow-hidden">
              <button
                onClick={() => setQuestionTopicsOpen((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50 transition-colors"
              >
                <span>
                  {t2('interview.questionTopics')}{' '}
                  <span className="text-muted-foreground">
                    ({selectedQuestionTopics.size}/{allQuestionTopicIds.length})
                  </span>
                </span>
                {questionTopicsOpen ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
              </button>
              {questionTopicsOpen && (
                <div className="border-t border-border px-4 py-3 space-y-3">
                  <div className="flex gap-3 text-xs">
                    <button
                      onClick={() => setSelectedQuestionTopics(new Set(allQuestionTopicIds))}
                      className="text-primary hover:underline"
                    >
                      {t2('interview.selectAll')}
                    </button>
                    <button
                      onClick={() => setSelectedQuestionTopics(new Set())}
                      className="text-muted-foreground hover:underline"
                    >
                      {t2('interview.deselectAll')}
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto">
                    {allQuestionTopicIds.map((id) => (
                      <label
                        key={id}
                        className="flex items-center gap-2 text-xs cursor-pointer select-none"
                      >
                        <input
                          type="checkbox"
                          checked={selectedQuestionTopics.has(id)}
                          onChange={() => toggleQuestionTopic(id)}
                          className="h-3.5 w-3.5 rounded border-border"
                        />
                        <span className="truncate">{getTopicLabel(id)}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Task topics */}
            <div className="border border-border rounded-md overflow-hidden">
              <button
                onClick={() => setTaskTopicsOpen((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50 transition-colors"
              >
                <span>
                  {t2('interview.taskTopics')}{' '}
                  <span className="text-muted-foreground">
                    ({selectedTaskTopics.size}/{allTaskTopicIds.length})
                  </span>
                </span>
                {taskTopicsOpen ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
              </button>
              {taskTopicsOpen && (
                <div className="border-t border-border px-4 py-3 space-y-3">
                  <div className="flex gap-3 text-xs">
                    <button
                      onClick={() => setSelectedTaskTopics(new Set(allTaskTopicIds))}
                      className="text-primary hover:underline"
                    >
                      {t2('interview.selectAll')}
                    </button>
                    <button
                      onClick={() => setSelectedTaskTopics(new Set())}
                      className="text-muted-foreground hover:underline"
                    >
                      {t2('interview.deselectAll')}
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    {allTaskTopicIds.map((id) => (
                      <label
                        key={id}
                        className="flex items-center gap-2 text-xs cursor-pointer select-none"
                      >
                        <input
                          type="checkbox"
                          checked={selectedTaskTopics.has(id)}
                          onChange={() => toggleTaskTopic(id)}
                          className="h-3.5 w-3.5 rounded border-border"
                        />
                        <span className="truncate">{getTopicLabel(id)}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Live estimate */}
      <div className="rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
        {t2('interview.estimateLabel')}:{' '}
        <span className="text-foreground font-medium">
          ~{estimate.questionCount} {t2('interview.questions')},{' '}
          {estimate.taskCount} {t2('interview.tasks')},{' '}
          ~{estimate.estimatedMinutes} {t2('interview.min')}
        </span>
      </div>

      {/* Start button */}
      <Button size="lg" className="w-full" onClick={handleStart}>
        {t2('interview.startBtn')}
      </Button>
    </div>
  );
}
