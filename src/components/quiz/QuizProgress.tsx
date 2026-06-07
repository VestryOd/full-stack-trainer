'use client';

import { Progress } from '@/components/ui/progress';
import { useLocale } from '@/context/LocaleContext';

interface QuizProgressProps {
  current: number;
  total: number;
  correct: number;
}

export function QuizProgress({ current, total, correct }: QuizProgressProps) {
  const { t2 } = useLocale();
  const percent = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>
          {t2('quiz.questionOf')} {current} {t2('quiz.of')} {total}
        </span>
        <span>
          {t2('quiz.correct')}: {correct}/{current > 0 ? current - 1 : 0}
        </span>
      </div>
      <Progress value={percent} className="h-2" />
    </div>
  );
}
