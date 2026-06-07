'use client';

import { useState } from 'react';
import { QuizCard, type QuizQuestionWithHtml } from '@/components/quiz/QuizCard';
import { QuizProgress } from '@/components/quiz/QuizProgress';
import { QuizResult } from '@/components/quiz/QuizResult';
import { Button } from '@/components/ui/button';
import { useLocale } from '@/context/LocaleContext';

interface QuizSessionProps {
  initialQuestions: QuizQuestionWithHtml[];
}

function dedupeById(questions: QuizQuestionWithHtml[]): QuizQuestionWithHtml[] {
  const seen = new Set<string>();
  return questions.filter((q) => {
    if (seen.has(q.id)) return false;
    seen.add(q.id);
    return true;
  });
}

export function QuizSession({ initialQuestions }: QuizSessionProps) {
  const { t2 } = useLocale();
  const [questions] = useState<QuizQuestionWithHtml[]>(() => dedupeById(initialQuestions));
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [correct, setCorrect] = useState(0);
  const [finished, setFinished] = useState(false);

  if (questions.length === 0) {
    return (
      <div className="container py-8 max-w-2xl">
        <p className="text-muted-foreground text-center py-12">
          {t2('quiz.noQuestions')}
        </p>
      </div>
    );
  }

  if (finished) {
    return (
      <div className="container py-8 max-w-2xl">
        <QuizResult correct={correct} total={questions.length} />
      </div>
    );
  }

  const current = questions[currentIndex];

  function handleSelect(index: number) {
    setSelectedIndex(index);
    if (index === current.correctIndex) setCorrect((c) => c + 1);
  }

  function handleNext() {
    if (currentIndex + 1 >= questions.length) {
      setFinished(true);
    } else {
      setCurrentIndex((i) => i + 1);
      setSelectedIndex(null);
    }
  }

  return (
    <div className="container py-8 max-w-2xl space-y-6">
      <QuizProgress current={currentIndex + 1} total={questions.length} correct={correct} />
      <QuizCard question={current} selectedIndex={selectedIndex} onSelect={handleSelect} />
      {selectedIndex !== null && (
        <div className="flex justify-end">
          <Button onClick={handleNext}>
            {currentIndex + 1 >= questions.length ? t2('quiz.seeResults') : t2('quiz.nextQuestion')}
          </Button>
        </div>
      )}
    </div>
  );
}
