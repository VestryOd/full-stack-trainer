'use client';

import { useState } from 'react';
import type { Question } from '@/types';
import { useLocale } from '@/context/LocaleContext';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DifficultyBadge } from './DifficultyBadge';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface QuestionCardProps {
  question: Question;
}

export function QuestionCard({ question }: QuestionCardProps) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-4">
          <p className="font-medium text-sm leading-relaxed">{t(question.question)}</p>
          <DifficultyBadge difficulty={question.difficulty} />
        </div>
      </CardHeader>
      <CardContent>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen((v) => !v)}
          className="mb-2 gap-1 text-muted-foreground"
        >
          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          {open ? 'Hide answer' : 'Show answer'}
        </Button>
        {open && (
          <div className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
            {t(question.answer)}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
