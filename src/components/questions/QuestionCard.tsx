'use client';

import { useState, useCallback, useEffect } from 'react';
import type { Question } from '@/types';
import type { Locale } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { DifficultyBadge } from './DifficultyBadge';
import { useQuestionReviewed } from '@/lib/progress';
import { ChevronDown, CheckCircle2, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

/** Question with its answer markdown pre-rendered to HTML (shiki github-dark) on the server. */
export interface QuestionWithAnswerHtml extends Question {
  answerHtml: { en: string; ru: string };
}

interface QuestionCardProps {
  question: QuestionWithAnswerHtml;
}

export function QuestionCard({ question }: QuestionCardProps) {
  const { locale: globalLocale, t2 } = useLocale();
  const [locale, setLocale] = useState<Locale>(globalLocale);
  const [open, setOpen] = useState(false);
  const [reviewed, toggleReviewed] = useQuestionReviewed(question.id);

  // Stay in sync with global locale changes
  useEffect(() => {
    setLocale(globalLocale);
  }, [globalLocale]);

  const questionText = question.question[locale];
  const answerHtml = question.answerHtml[locale];

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      setOpen((v) => !v);
    }
  }, []);

  return (
    <div
      className={cn(
        'border rounded-md transition-colors',
        reviewed ? 'border-green-500/30 bg-green-500/[0.03]' : 'border-border bg-card',
      )}
    >
      {/* Card header */}
      <div className="px-4 pt-3 pb-2">
        {/* Tags row */}
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <DifficultyBadge difficulty={question.difficulty} />
          {question.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-mono text-muted-foreground bg-muted"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Question + controls row */}
        <div className="flex items-start gap-3">
          <p className="flex-1 text-sm leading-relaxed font-medium">{questionText}</p>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            {/* Per-card locale toggle */}
            <div className="flex rounded border border-border overflow-hidden text-xs font-mono">
              <button
                onClick={() => setLocale('en')}
                className={cn(
                  'px-1.5 py-0.5 transition-colors',
                  locale === 'en'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                aria-label="Show in English"
              >
                EN
              </button>
              <button
                onClick={() => setLocale('ru')}
                className={cn(
                  'px-1.5 py-0.5 transition-colors',
                  locale === 'ru'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                aria-label="Show in Russian"
              >
                RU
              </button>
            </div>

            {/* Accordion toggle */}
            <button
              onClick={() => setOpen((v) => !v)}
              onKeyDown={handleKeyDown}
              aria-expanded={open}
              aria-controls={`answer-${question.id}`}
              className="rounded p-0.5 text-muted-foreground hover:text-foreground transition-colors"
              aria-label={open ? t2('questions.hideAnswer') : t2('questions.showAnswer')}
            >
              <ChevronDown
                className={cn('h-4 w-4 transition-transform duration-200', open && 'rotate-180')}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Accordion answer */}
      {open && (
        <div id={`answer-${question.id}`} className="question-answer border-t border-border px-4 py-3 animate-fade-in">
          <div className="article-body text-sm" dangerouslySetInnerHTML={{ __html: answerHtml }} />

          {/* Mark as reviewed */}
          <div className="mt-3 pt-3 border-t border-border flex justify-end">
            <button
              onClick={toggleReviewed}
              className={cn(
                'flex items-center gap-1.5 text-xs transition-colors',
                reviewed
                  ? 'text-green-500 hover:text-green-400'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              aria-label={reviewed ? 'Mark as not reviewed' : t2('questions.markReviewed')}
            >
              {reviewed ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {t2('questions.reviewed')}
                </>
              ) : (
                <>
                  <Circle className="h-3.5 w-3.5" />
                  {t2('questions.markReviewed')}
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
