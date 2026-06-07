'use client';

import type { QuizQuestion } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface QuizCardProps {
  question: QuizQuestion;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}

export function QuizCard({ question, selectedIndex, onSelect }: QuizCardProps) {
  const { t, t2 } = useLocale();
  const options = t({ en: question.options.en.join('|||'), ru: question.options.ru.join('|||') }).split('|||');
  const answered = selectedIndex !== null;

  return (
    <div className="space-y-4">
      <p className="font-medium text-lg leading-relaxed">{t(question.question)}</p>
      <div className="flex flex-col gap-2">
        {options.map((option, idx) => (
          <Button
            key={idx}
            variant="outline"
            className={cn(
              'justify-start h-auto py-3 px-4 text-left whitespace-normal',
              answered && idx === question.correctIndex && 'border-green-500 bg-green-50 dark:bg-green-950',
              answered && selectedIndex === idx && idx !== question.correctIndex && 'border-red-500 bg-red-50 dark:bg-red-950',
            )}
            onClick={() => !answered && onSelect(idx)}
            disabled={answered}
          >
            <span className="mr-2 font-mono text-xs text-muted-foreground">
              {String.fromCharCode(65 + idx)}.
            </span>
            {option}
          </Button>
        ))}
      </div>
      {answered && (
        <div className="rounded-md border p-3 text-sm bg-muted">
          <p className="font-medium mb-1">{t2('quiz.explanation')}:</p>
          <p className="text-muted-foreground">{t(question.explanation)}</p>
        </div>
      )}
    </div>
  );
}
