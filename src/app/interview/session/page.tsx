'use client';

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { marked } from 'marked';
import Link from 'next/link';
import type { Question, Task } from '@/types';
import type { InterviewPlan, InterviewItem } from '@/lib/interview';
import { useLocale } from '@/context/LocaleContext';
import { DifficultyBadge } from '@/components/questions/DifficultyBadge';
import { SolutionSpoiler } from '@/components/tasks/SolutionSpoiler';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

const SESSION_KEY = 'fst-interview-plan';

const TASK_DIFFICULTY_COLORS = {
  easy:   'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  hard:   'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
} as const;

// Plain markdown render — instant, used as initial fallback before Shiki loads
function renderMarkdown(text: string): string {
  let html = marked(text, { async: false }) as string;
  // Apply Shiki-style dark container so code blocks are readable before Shiki is ready
  html = html.replace(
    /<pre><code(?: class="language-[^"]*")?>([\s\S]*?)<\/code><\/pre>/g,
    '<pre class="shiki github-dark" style="background-color:#24292e;color:#e1e4e8"><code>$1</code></pre>',
  );
  return html;
}

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
  const s = (totalSeconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

// Shiki helpers — dynamically imported so they don't bloat the initial bundle
async function renderWithShiki(markdown: string): Promise<string> {
  const { renderArticleHtml } = await import('@/components/theory/ArticleRenderer');
  return renderArticleHtml(markdown);
}

async function highlightCode(code: string): Promise<string> {
  const { highlight } = await import('@/lib/highlight');
  return highlight(code, 'typescript');
}

// ─── Timer (self-contained — re-renders only itself, not the whole page) ─────

function TimerDisplay({ t2 }: { t2: (key: string) => string }) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="font-mono text-sm tabular-nums">
      {t2('interview.elapsed')}: {formatTime(elapsed)}
    </span>
  );
}

// ─── Question Item ────────────────────────────────────────────────────────────

interface QuestionItemProps {
  item: InterviewItem;
  onReviewed: () => void;
}

function InterviewQuestionItem({ item, onReviewed }: QuestionItemProps) {
  const { locale, t2 } = useLocale();
  const question = item.data as Question;
  const [showAnswer, setShowAnswer] = useState(false);

  // Plain html — rendered immediately for instant display
  const plainHtml = useMemo(
    () => ({ en: renderMarkdown(question.answer.en), ru: renderMarkdown(question.answer.ru) }),
    [question.answer.en, question.answer.ru],
  );

  // Shiki-enhanced html — loaded asynchronously on mount
  const [shikiHtml, setShikiHtml] = useState<{ en: string; ru: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      renderWithShiki(question.answer.en),
      renderWithShiki(question.answer.ru),
    ])
      .then(([en, ru]) => { if (!cancelled) setShikiHtml({ en, ru }); })
      .catch(() => { /* keep plain fallback */ });
    return () => { cancelled = true; };
  }, [question.answer.en, question.answer.ru]);

  const answerHtml = (shikiHtml ?? plainHtml)[locale];

  function handleToggle() {
    if (!showAnswer) onReviewed();
    setShowAnswer((v) => !v);
  }

  return (
    <div className="border border-border rounded-md bg-card">
      <div className="px-4 pt-3 pb-3">
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <DifficultyBadge difficulty={question.difficulty} />
          <Badge variant="secondary" className="text-xs font-mono capitalize">
            {item.topicId}
          </Badge>
          {question.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-mono text-muted-foreground bg-muted"
            >
              {tag}
            </span>
          ))}
        </div>
        <p className="text-sm leading-relaxed font-medium">{question.question[locale]}</p>

        <div className="mt-3">
          <button
            onClick={handleToggle}
            className={cn(
              'text-xs font-medium px-3 py-1.5 rounded border transition-colors',
              showAnswer
                ? 'border-primary/40 text-primary hover:bg-primary/5'
                : 'border-border text-muted-foreground hover:text-foreground hover:border-foreground/30',
            )}
          >
            {showAnswer ? t2('interview.hideAnswer') : t2('interview.showAnswer')}
          </button>
        </div>
      </div>

      {showAnswer && (
        <div className="border-t border-border px-4 py-3">
          <div
            className="article-body text-sm"
            dangerouslySetInnerHTML={{ __html: answerHtml }}
          />
        </div>
      )}
    </div>
  );
}

// ─── Task Item ────────────────────────────────────────────────────────────────

interface TaskItemProps {
  item: InterviewItem;
  onReviewed: () => void;
}

function InterviewTaskItem({ item, onReviewed }: TaskItemProps) {
  const { locale, t2 } = useLocale();
  const task = item.data as Task;

  // Description: show plain immediately, replace with Shiki when ready
  const plainDescription = useMemo(
    () => ({ en: renderMarkdown(task.description.en), ru: renderMarkdown(task.description.ru) }),
    [task.description.en, task.description.ru],
  );
  const [shikiDescription, setShikiDescription] = useState<{ en: string; ru: string } | null>(null);

  // Solution explanation: same pattern
  const plainExplanation = useMemo(
    () => ({
      en: renderMarkdown(task.solutionExplanation.en),
      ru: renderMarkdown(task.solutionExplanation.ru),
    }),
    [task.solutionExplanation.en, task.solutionExplanation.ru],
  );
  const [shikiExplanation, setShikiExplanation] = useState<{ en: string; ru: string } | null>(null);

  // Raw code: highlighted with Shiki; show plain <pre> until ready
  const [starterHtml, setStarterHtml] = useState<string | null>(null);
  const [solutionHtml, setSolutionHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      renderWithShiki(task.description.en),
      renderWithShiki(task.description.ru),
    ])
      .then(([en, ru]) => { if (!cancelled) setShikiDescription({ en, ru }); })
      .catch(() => {});

    Promise.all([
      renderWithShiki(task.solutionExplanation.en),
      renderWithShiki(task.solutionExplanation.ru),
    ])
      .then(([en, ru]) => { if (!cancelled) setShikiExplanation({ en, ru }); })
      .catch(() => {});

    highlightCode(task.solution)
      .then((html) => { if (!cancelled) setSolutionHtml(html); })
      .catch(() => {});

    if (task.starterCode) {
      highlightCode(task.starterCode)
        .then((html) => { if (!cancelled) setStarterHtml(html); })
        .catch(() => {});
    }

    return () => { cancelled = true; };
  }, [task.description.en, task.description.ru, task.solution,
      task.solutionExplanation.en, task.solutionExplanation.ru, task.starterCode]);

  const descriptionHtml = (shikiDescription ?? plainDescription)[locale];
  const explanationHtml = (shikiExplanation ?? plainExplanation)[locale];

  return (
    <div className="border border-border rounded-md bg-card">
      <div className="px-4 pt-3 pb-3">
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <Badge variant="outline" className="text-xs">
            {t2('interview.taskLabel')}
          </Badge>
          <Badge
            variant="outline"
            className={cn('text-xs capitalize', TASK_DIFFICULTY_COLORS[task.difficulty])}
          >
            {task.difficulty}
          </Badge>
          <Badge variant="secondary" className="text-xs font-mono capitalize">
            {item.topicId}
          </Badge>
        </div>
        <h3 className="text-base font-semibold">{task.title[locale]}</h3>
        <div
          className="article-body text-sm mt-2"
          dangerouslySetInnerHTML={{ __html: descriptionHtml }}
        />
      </div>

      {task.starterCode && (
        <div className="border-t border-border px-4 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {t2('tasks.starterCode')}
          </p>
          {starterHtml ? (
            <div className="overflow-x-auto text-sm" dangerouslySetInnerHTML={{ __html: starterHtml }} />
          ) : (
            <pre className="shiki github-dark" style={{ backgroundColor: '#24292e', color: '#e1e4e8' }}>
              <code>{task.starterCode}</code>
            </pre>
          )}
        </div>
      )}

      <div className="border-t border-border px-4 py-3">
        <SolutionSpoiler
          label={t2('tasks.showSolution')}
          hideLabel={t2('tasks.hideSolution')}
          revealLabel={t2('tasks.revealSolution')}
          onReveal={onReviewed}
        >
          {solutionHtml ? (
            <div className="overflow-x-auto text-sm" dangerouslySetInnerHTML={{ __html: solutionHtml }} />
          ) : (
            <pre className="shiki github-dark" style={{ backgroundColor: '#24292e', color: '#e1e4e8' }}>
              <code>{task.solution}</code>
            </pre>
          )}
          <div
            className="article-body text-sm"
            dangerouslySetInnerHTML={{ __html: explanationHtml }}
          />
        </SolutionSpoiler>
      </div>

      {task.tags.length > 0 && (
        <div className="border-t border-border px-4 py-2 flex flex-wrap gap-1">
          {task.tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="text-xs">
              {tag}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Summary Screen ───────────────────────────────────────────────────────────

interface SummaryProps {
  plan: InterviewPlan;
  elapsed: number;
  reviewedIndices: Set<number>;
}

function SummaryScreen({ plan, elapsed, reviewedIndices }: SummaryProps) {
  const { t2 } = useLocale();
  const router = useRouter();

  const questionItems = plan.sequence.filter((i) => i.type === 'question');
  const taskItems = plan.sequence.filter((i) => i.type === 'task');

  const reviewedQuestions = plan.sequence.filter(
    (item, idx) => item.type === 'question' && reviewedIndices.has(idx),
  ).length;
  const reviewedTasks = plan.sequence.filter(
    (item, idx) => item.type === 'task' && reviewedIndices.has(idx),
  ).length;

  const topicsCovered = [...new Set(plan.sequence.map((i) => i.topicId))];

  return (
    <div className="container py-8 max-w-2xl space-y-6">
      <h1 className="text-3xl font-bold">{t2('interview.summaryTitle')}</h1>

      <div className="grid grid-cols-2 gap-3">
        <div className="border border-border rounded-lg p-4">
          <p className="text-xs text-muted-foreground mb-1">{t2('interview.timeTaken')}</p>
          <p className="text-2xl font-bold font-mono">{formatTime(elapsed)}</p>
        </div>
        <div className="border border-border rounded-lg p-4">
          <p className="text-xs text-muted-foreground mb-1">{t2('interview.plannedDuration')}</p>
          <p className="text-2xl font-bold font-mono">
            {plan.totalMinutes} {t2('interview.min')}
          </p>
        </div>
      </div>

      <div className="border border-border rounded-lg divide-y divide-border">
        <div className="px-4 py-3 flex justify-between items-center">
          <span className="text-sm">{t2('interview.questionsReviewed')}</span>
          <span className="font-semibold">
            {reviewedQuestions} / {questionItems.length}
          </span>
        </div>
        <div className="px-4 py-3 flex justify-between items-center">
          <span className="text-sm">{t2('interview.tasksAttempted')}</span>
          <span className="font-semibold">
            {reviewedTasks} / {taskItems.length}
          </span>
        </div>
      </div>

      <div>
        <p className="text-sm font-medium mb-2">{t2('interview.topicsCovered')}</p>
        <div className="flex flex-wrap gap-1.5">
          {topicsCovered.map((topicId) => (
            <Badge key={topicId} variant="secondary" className="font-mono capitalize">
              {topicId}
            </Badge>
          ))}
        </div>
      </div>

      <div className="flex gap-3">
        <Button onClick={() => router.push('/interview')}>{t2('interview.startNew')}</Button>
        <Button variant="outline" asChild>
          <Link href="/">{t2('interview.backHome')}</Link>
        </Button>
      </div>
    </div>
  );
}

// ─── Main Session Page ────────────────────────────────────────────────────────

export default function InterviewSessionPage() {
  const { t2 } = useLocale();

  const [plan, setPlan] = useState<InterviewPlan | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [reviewedIndices, setReviewedIndices] = useState<Set<number>>(new Set());
  const [finished, setFinished] = useState(false);
  const [showEndConfirm, setShowEndConfirm] = useState(false);

  // Captures elapsed time at the moment the session ends (for summary display)
  const [finalElapsed, setFinalElapsed] = useState(0);
  const startTimeRef = useRef(Date.now());

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored) {
      try {
        setPlan(JSON.parse(stored) as InterviewPlan);
      } catch {
        // corrupt data — show no-session state
      }
    }
    setLoaded(true);
  }, []);

  const markReviewed = useCallback((index: number) => {
    setReviewedIndices((prev) => {
      if (prev.has(index)) return prev;
      const next = new Set(prev);
      next.add(index);
      return next;
    });
  }, []);

  function finishSession() {
    setFinalElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    setFinished(true);
  }

  function handleNext() {
    if (!plan) return;
    if (currentIndex + 1 >= plan.sequence.length) {
      finishSession();
    } else {
      setCurrentIndex((i) => i + 1);
    }
  }

  function handleEndConfirmed() {
    finishSession();
    setShowEndConfirm(false);
  }

  if (!loaded) {
    return (
      <div className="container py-8 max-w-2xl">
        <p className="text-muted-foreground text-center py-12">Loading…</p>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="container py-8 max-w-2xl text-center space-y-4">
        <p className="text-muted-foreground">{t2('interview.noSession')}</p>
        <Button asChild>
          <Link href="/interview">{t2('interview.startNew')}</Link>
        </Button>
      </div>
    );
  }

  if (finished) {
    return <SummaryScreen plan={plan} elapsed={finalElapsed} reviewedIndices={reviewedIndices} />;
  }

  const total = plan.sequence.length;
  const item = plan.sequence[currentIndex];
  const isLast = currentIndex + 1 >= total;
  const progressPercent = Math.round((currentIndex / total) * 100);

  return (
    <div className="container py-6 max-w-3xl space-y-5">
      {/* Top bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-muted-foreground">
            {t2('interview.itemOf')} {currentIndex + 1} {t2('interview.of')} {total}
          </span>
          <TimerDisplay t2={t2} />
          {!showEndConfirm && (
            <Button variant="outline" size="sm" onClick={() => setShowEndConfirm(true)}>
              {t2('interview.endInterview')}
            </Button>
          )}
        </div>
        <Progress value={progressPercent} className="h-1.5" />
      </div>

      {/* End-interview confirmation */}
      {showEndConfirm && (
        <div className="border border-destructive/30 bg-destructive/5 rounded-md px-4 py-3 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium">{t2('interview.endConfirmTitle')}</p>
            <p className="text-xs text-muted-foreground">{t2('interview.endConfirmDesc')}</p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <Button size="sm" variant="destructive" onClick={handleEndConfirmed}>
              {t2('interview.endConfirmYes')}
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowEndConfirm(false)}>
              {t2('interview.endConfirmNo')}
            </Button>
          </div>
        </div>
      )}

      {/* Current item — key resets component state on every navigation */}
      {item.type === 'question' ? (
        <InterviewQuestionItem
          key={currentIndex}
          item={item}
          onReviewed={() => markReviewed(currentIndex)}
        />
      ) : (
        <InterviewTaskItem
          key={currentIndex}
          item={item}
          onReviewed={() => markReviewed(currentIndex)}
        />
      )}

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <Button variant="ghost" size="sm" onClick={handleNext}>
          {t2('interview.skip')}
        </Button>
        <Button onClick={isLast ? finishSession : handleNext}>
          {isLast ? t2('interview.finish') : t2('interview.next')}
        </Button>
      </div>
    </div>
  );
}
