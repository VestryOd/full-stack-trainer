'use client';

import { Button } from '@/components/ui/button';
import { useLocale } from '@/context/LocaleContext';
import Link from 'next/link';

interface QuizResultProps {
  correct: number;
  total: number;
}

export function QuizResult({ correct, total }: QuizResultProps) {
  const { t2 } = useLocale();
  const percent = total > 0 ? Math.round((correct / total) * 100) : 0;

  return (
    <div className="text-center space-y-4 py-8">
      <div className="text-5xl font-bold text-primary">{percent}%</div>
      <p className="text-muted-foreground">
        {t2('quiz.yourScore').replace('{correct}', String(correct)).replace('{total}', String(total))}
      </p>
      <div className="flex justify-center gap-3">
        <Button asChild variant="outline">
          <Link href="/quiz">{t2('quiz.newQuiz')}</Link>
        </Button>
      </div>
    </div>
  );
}
