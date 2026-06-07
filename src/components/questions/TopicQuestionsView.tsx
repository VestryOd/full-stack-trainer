'use client';

import Link from 'next/link';
import type { Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { QuestionFilters } from './QuestionFilters';
import type { QuestionWithAnswerHtml } from './QuestionCard';
import { ChevronRight } from 'lucide-react';

interface TopicQuestionsViewProps {
  topic: Topic;
  questions: QuestionWithAnswerHtml[];
}

export function TopicQuestionsView({ topic, questions }: TopicQuestionsViewProps) {
  const { t2 } = useLocale();

  return (
    <div className="container py-8 space-y-6 max-w-4xl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
        <Link href="/questions" className="hover:text-foreground transition-colors">{t2('questions.title')}</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">{topic.label}</span>
      </nav>

      <div>
        <h1 className="text-2xl font-mono font-semibold">{topic.label}</h1>
        <p className="text-muted-foreground text-sm mt-1">{questions.length} {t2('questions.questionsWord')}</p>
      </div>

      {questions.length > 0 ? (
        <QuestionFilters questions={questions} topicLabel={topic.label} />
      ) : (
        <p className="text-center text-muted-foreground py-12 text-sm">
          {t2('questions.noQuestionsYet')}
        </p>
      )}
    </div>
  );
}
