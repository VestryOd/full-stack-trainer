import { Badge } from '@/components/ui/badge';
import type { QuestionDifficulty } from '@/types';
import { cn } from '@/lib/utils';

const DIFFICULTY_STYLES: Record<QuestionDifficulty, string> = {
  junior:   'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  middle:   'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  senior:   'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  advanced: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

interface DifficultyBadgeProps {
  difficulty: QuestionDifficulty;
}

export function DifficultyBadge({ difficulty }: DifficultyBadgeProps) {
  return (
    <Badge variant="outline" className={cn('capitalize', DIFFICULTY_STYLES[difficulty])}>
      {difficulty}
    </Badge>
  );
}
