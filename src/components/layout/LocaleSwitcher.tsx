'use client';

import { useLocale } from '@/context/LocaleContext';
import { cn } from '@/lib/utils';

export function LocaleSwitcher() {
  const { locale, setLocale } = useLocale();

  return (
    <div className="flex rounded border border-border overflow-hidden text-xs font-mono">
      {(['en', 'ru'] as const).map((l) => (
        <button
          key={l}
          onClick={() => setLocale(l)}
          className={cn(
            'px-2.5 py-1 uppercase transition-colors',
            locale === l
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent',
          )}
          aria-label={l === 'en' ? 'Switch to English' : 'Switch to Russian'}
        >
          {l}
        </button>
      ))}
    </div>
  );
}
