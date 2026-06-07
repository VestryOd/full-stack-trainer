'use client';

import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useLocale } from '@/context/LocaleContext';

interface SolutionSpoilerProps {
  children: React.ReactNode;
  label?: string;
  hideLabel?: string;
  revealLabel?: string;
}

export function SolutionSpoiler({ children, label, hideLabel, revealLabel }: SolutionSpoilerProps) {
  const { t2 } = useLocale();
  const [revealed, setRevealed] = useState(false);

  const showLabel = label ?? t2('tasks.showSolution');
  const hiddenLabel = hideLabel ?? t2('tasks.hideSolution');
  const revealActionLabel = revealLabel ?? t2('tasks.revealSolution');

  return (
    <div className="relative border border-border rounded-md overflow-hidden">
      {/* Header toggle */}
      <button
        onClick={() => setRevealed((v) => !v)}
        aria-expanded={revealed}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors border-b border-border"
      >
        <span className="font-mono">{revealed ? hiddenLabel : showLabel}</span>
        {revealed ? (
          <EyeOff className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <Eye className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
      </button>

      {/* Content with blur overlay when hidden */}
      <div className="relative">
        <div
          className="p-4 space-y-4 transition-all duration-200"
          style={{
            filter: revealed ? 'none' : 'blur(6px)',
            userSelect: revealed ? 'auto' : 'none',
            pointerEvents: revealed ? 'auto' : 'none',
          }}
        >
          {children}
        </div>

        {/* Blur overlay click-to-reveal */}
        {!revealed && (
          <div
            className="absolute inset-0 flex items-center justify-center cursor-pointer"
            onClick={() => setRevealed(true)}
            role="button"
            aria-label={revealActionLabel}
          >
            <Button variant="default" size="sm" className="shadow-lg pointer-events-none">
              <Eye className="h-4 w-4 mr-2" />
              {revealActionLabel}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
