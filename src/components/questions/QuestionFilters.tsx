'use client';

import { useState, useMemo } from 'react';
import type { QuestionDifficulty } from '@/types';
import { QuestionCard, type QuestionWithAnswerHtml } from './QuestionCard';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { useLocale } from '@/context/LocaleContext';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Search, X, ChevronRight } from 'lucide-react';

interface QuestionFiltersProps {
  questions: QuestionWithAnswerHtml[];
  showTopicFilter?: boolean;
  topicLabel?: string;
}

const DIFFICULTIES: QuestionDifficulty[] = ['junior', 'middle', 'senior', 'advanced'];

const DIFFICULTY_ORDER: Record<QuestionDifficulty, number> = {
  junior: 0,
  middle: 1,
  senior: 2,
  advanced: 3,
};

const DIFFICULTY_STYLES: Record<QuestionDifficulty, string> = {
  junior:   'data-[active=true]:bg-green-500/20 data-[active=true]:text-green-400 data-[active=true]:border-green-500/40',
  middle:   'data-[active=true]:bg-blue-500/20 data-[active=true]:text-blue-400 data-[active=true]:border-blue-500/40',
  senior:   'data-[active=true]:bg-orange-500/20 data-[active=true]:text-orange-400 data-[active=true]:border-orange-500/40',
  advanced: 'data-[active=true]:bg-red-500/20 data-[active=true]:text-red-400 data-[active=true]:border-red-500/40',
};

export function QuestionFilters({ questions, topicLabel }: QuestionFiltersProps) {
  const { t2 } = useLocale();
  const [search, setSearch] = useState('');
  const [activeDifficulties, setActiveDifficulties] = useState<Set<QuestionDifficulty>>(new Set());
  const [activeTags, setActiveTags] = useState<Set<string>>(new Set());
  const [tagsOpen, setTagsOpen] = useState(false);

  // Collect all tags from the question set
  const allTags = useMemo(() => {
    const s = new Set<string>();
    questions.forEach((q) => (q.tags ?? []).forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [questions]);

  const filtered = useMemo(() => {
    return questions
      .filter((q) => {
        if (activeDifficulties.size > 0 && !activeDifficulties.has(q.difficulty)) return false;
        if (activeTags.size > 0 && !(q.tags ?? []).some((t) => activeTags.has(t))) return false;
        if (search) {
          const needle = search.toLowerCase();
          const haystack = `${q.question.en} ${q.question.ru} ${(q.tags ?? []).join(' ')}`.toLowerCase();
          if (!haystack.includes(needle)) return false;
        }
        return true;
      })
      .sort((a, b) => DIFFICULTY_ORDER[a.difficulty] - DIFFICULTY_ORDER[b.difficulty]);
  }, [questions, activeDifficulties, activeTags, search]);

  function toggleDifficulty(d: QuestionDifficulty) {
    setActiveDifficulties((prev) => {
      const next = new Set(prev);
      if (next.has(d)) next.delete(d); else next.add(d);
      return next;
    });
  }

  function toggleTag(tag: string) {
    setActiveTags((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag); else next.add(tag);
      return next;
    });
  }

  function reset() {
    setSearch('');
    setActiveDifficulties(new Set());
    setActiveTags(new Set());
  }

  const hasFilters = search || activeDifficulties.size > 0 || activeTags.size > 0;

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="space-y-3 p-4 bg-card border border-border rounded-md">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder={t2('questions.search')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-sm bg-background"
          />
        </div>

        {/* Difficulty pills */}
        <div className="flex flex-wrap gap-1.5">
          {DIFFICULTIES.map((d) => (
            <button
              key={d}
              data-active={activeDifficulties.has(d)}
              onClick={() => toggleDifficulty(d)}
              className={cn(
                'rounded px-2 py-0.5 text-xs font-mono border border-border text-muted-foreground capitalize transition-colors hover:border-muted-foreground',
                DIFFICULTY_STYLES[d],
              )}
            >
              {d}
            </button>
          ))}
        </div>

        {/* Tag pills (collapsible) */}
        {allTags.length > 0 && (
          <Collapsible open={tagsOpen} onOpenChange={setTagsOpen}>
            <CollapsibleTrigger asChild>
              <button className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
                <ChevronRight className={cn('h-3 w-3 transition-transform duration-200', tagsOpen && 'rotate-90')} />
                {tagsOpen ? t2('questions.hideTags') : t2('questions.showTags')}
                {activeTags.size > 0 && ` (${activeTags.size})`}
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
              <div className="flex flex-wrap gap-1 pt-2">
                {allTags.map((tag) => (
                  <button
                    key={tag}
                    data-active={activeTags.has(tag)}
                    onClick={() => toggleTag(tag)}
                    className={cn(
                      'rounded px-1.5 py-0.5 text-xs font-mono border border-border text-muted-foreground transition-colors hover:border-muted-foreground',
                      activeTags.has(tag) && 'bg-primary/10 text-primary border-primary/30',
                    )}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Count + reset */}
        <div className="flex items-center justify-between pt-1 border-t border-border">
          <span className="text-xs text-muted-foreground font-mono">
            {filtered.length} / {questions.length}{' '}
            {topicLabel ? `${t2('questions.progress')} ${topicLabel}` : t2('questions.questionsWord')}
          </span>
          {hasFilters && (
            <button
              onClick={reset}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-3 w-3" />
              {t2('questions.reset')}
            </button>
          )}
        </div>
      </div>

      {/* Question list */}
      {filtered.length === 0 ? (
        <p className="text-center text-muted-foreground py-8 text-sm">No questions match the filters.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((q) => (
            <QuestionCard key={q.id} question={q} />
          ))}
        </div>
      )}
    </div>
  );
}
