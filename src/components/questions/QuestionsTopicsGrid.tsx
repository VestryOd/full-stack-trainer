'use client';

import Link from 'next/link';
import type { Topic } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { cn } from '@/lib/utils';
import { BookOpen, ChevronRight } from 'lucide-react';

const LEVEL_STYLES = {
  deep:   'bg-blue-500/10 text-blue-400 border-blue-500/20',
  medium: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  light:  'bg-muted text-muted-foreground border-border',
};

interface TopicWithCount extends Topic {
  count: number;
}

interface QuestionsTopicsGridProps {
  topicsWithCounts: TopicWithCount[];
  totalQuestions: number;
}

export function QuestionsTopicsGrid({ topicsWithCounts, totalQuestions }: QuestionsTopicsGridProps) {
  const { t2 } = useLocale();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-mono font-semibold">{t2('questions.title')}</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {totalQuestions} {t2('questions.subtitle')} {topicsWithCounts.length} {t2('questions.topicsWord')}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {topicsWithCounts.map((topic) => (
          <Link
            key={topic.id}
            href={`/questions/${topic.id}`}
            className="group flex items-center justify-between p-4 bg-card border border-border rounded-md hover:border-muted-foreground/50 transition-colors"
          >
            <div className="flex items-start gap-3">
              <BookOpen className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium group-hover:text-foreground transition-colors">
                  {topic.label}
                </p>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">
                  {topic.count} {t2('questions.questionsWord')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border',
                  LEVEL_STYLES[topic.level],
                )}
              >
                {topic.level}
              </span>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
