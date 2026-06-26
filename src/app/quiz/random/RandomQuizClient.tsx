'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import type { QuizQuestion } from '@/types';
import type { QuizQuestionWithHtml } from '@/components/quiz/QuizCard';
import { QuizSession } from '@/app/quiz/[sessionId]/QuizSession';
import { fisherYates, shuffleOptions, dedupeById } from '@/lib/quiz-utils';
import { Button } from '@/components/ui/button';
import { useLocale } from '@/context/LocaleContext';

const RANDOM_QUIZ_KEY = 'fst-quiz-random';
const MAX_BADGE_LABELS = 3;

interface RandomQuizConfig {
  topicIds: string[];
  count: number;
}

interface Props {
  allQuestionsPerTopic: Record<string, QuizQuestion[]>;
  topicLabels: Record<string, string>;
}

export function RandomQuizClient({ allQuestionsPerTopic, topicLabels }: Props) {
  const { t2 } = useLocale();
  const [questionsWithHtml, setQuestionsWithHtml] = useState<QuizQuestionWithHtml[] | null>(null);
  const [topicBadge, setTopicBadge] = useState('');
  const [noSession, setNoSession] = useState(false);

  useEffect(() => {
    const raw = sessionStorage.getItem(RANDOM_QUIZ_KEY);
    if (!raw) {
      setNoSession(true);
      return;
    }

    let config: RandomQuizConfig;
    try {
      config = JSON.parse(raw) as RandomQuizConfig;
    } catch {
      setNoSession(true);
      return;
    }

    const { topicIds, count } = config;

    // Build topic badge string
    const labels = topicIds.map((id) => topicLabels[id] ?? id);
    const badge =
      labels.length <= MAX_BADGE_LABELS
        ? labels.join(', ')
        : `${labels.slice(0, MAX_BADGE_LABELS).join(', ')} +${labels.length - MAX_BADGE_LABELS}`;
    setTopicBadge(badge);

    // Merge, dedupe, shuffle, slice
    const pool = topicIds.flatMap((id) => allQuestionsPerTopic[id] ?? []);
    const selected = fisherYates(dedupeById(pool)).slice(0, count).map(shuffleOptions);

    // Pre-render all selected questions with Shiki before showing the quiz
    (async () => {
      try {
        const { renderArticleHtml } = await import('@/components/theory/ArticleRenderer');
        const withHtml: QuizQuestionWithHtml[] = await Promise.all(
          selected.map(async (q) => ({
            ...q,
            questionHtml: {
              en: await renderArticleHtml(q.question.en),
              ru: await renderArticleHtml(q.question.ru ?? q.question.en),
            },
          })),
        );
        setQuestionsWithHtml(withHtml);
      } catch {
        // Shiki failed — fall back to plain text wrapped in a paragraph
        const withPlain: QuizQuestionWithHtml[] = selected.map((q) => ({
          ...q,
          questionHtml: {
            en: `<p>${q.question.en}</p>`,
            ru: `<p>${q.question.ru ?? q.question.en}</p>`,
          },
        }));
        setQuestionsWithHtml(withPlain);
      }
    })();
  }, [allQuestionsPerTopic, topicLabels]);

  if (noSession) {
    return (
      <div className="container py-8 max-w-2xl text-center space-y-4">
        <p className="text-muted-foreground">{t2('quiz.randomNoSession')}</p>
        <Button asChild>
          <Link href="/quiz">{t2('quiz.newQuiz')}</Link>
        </Button>
      </div>
    );
  }

  if (!questionsWithHtml) {
    return (
      <div className="container max-w-2xl text-center py-24">
        <p className="text-muted-foreground">{t2('quiz.randomLoading')}</p>
      </div>
    );
  }

  return <QuizSession initialQuestions={questionsWithHtml} topicBadge={topicBadge} />;
}
