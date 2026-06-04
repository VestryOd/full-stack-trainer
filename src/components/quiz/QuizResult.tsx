import { Button } from '@/components/ui/button';
import Link from 'next/link';

interface QuizResultProps {
  correct: number;
  total: number;
}

export function QuizResult({ correct, total }: QuizResultProps) {
  const percent = total > 0 ? Math.round((correct / total) * 100) : 0;

  return (
    <div className="text-center space-y-4 py-8">
      <div className="text-5xl font-bold text-primary">{percent}%</div>
      <p className="text-muted-foreground">
        You answered {correct} out of {total} questions correctly.
      </p>
      <div className="flex justify-center gap-3">
        <Button asChild variant="outline">
          <Link href="/quiz">New Quiz</Link>
        </Button>
      </div>
    </div>
  );
}
