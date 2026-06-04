import type { Question } from '@/types';
import { QuestionCard } from './QuestionCard';

interface QuestionListProps {
  questions: Question[];
}

export function QuestionList({ questions }: QuestionListProps) {
  if (questions.length === 0) {
    return <p className="text-center text-muted-foreground py-8">No questions found.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {questions.map((q) => (
        <QuestionCard key={q.id} question={q} />
      ))}
    </div>
  );
}
