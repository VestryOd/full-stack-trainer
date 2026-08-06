'use client';

import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLocale } from '@/context/LocaleContext';
import { Button } from '@/components/ui/button';
import { useSearchDialog } from './SearchProvider';

/** Returns the platform-appropriate shortcut hint (⌘K on mac, Ctrl K elsewhere). */
function useShortcutHint(): string {
  const [hint, setHint] = useState('⌘K');
  useEffect(() => {
    const isMac = /mac|iphone|ipad|ipod/i.test(navigator.platform || navigator.userAgent);
    setHint(isMac ? '⌘K' : 'Ctrl K');
  }, []);
  return hint;
}

/**
 * Search entry point for the navbar:
 * - desktop (md+): a fake search field with a shortcut hint;
 * - mobile: a compact icon button.
 * Both open the shared command palette.
 */
export function SearchTrigger({ className }: { className?: string }) {
  const { setOpen } = useSearchDialog();
  const { t2 } = useLocale();
  const hint = useShortcutHint();

  return (
    <>
      {/* Desktop: fake input */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          'hidden shrink-0 items-center gap-2 whitespace-nowrap rounded-md border border-border bg-muted/40 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted md:flex',
          className,
        )}
        aria-label={t2('search.title')}
      >
        <Search className="h-4 w-4" />
        <span className="hidden lg:inline">{t2('search.title')}</span>
        <kbd className="ml-2 hidden rounded border border-border bg-background px-1.5 font-mono text-[10px] lg:inline">
          {hint}
        </kbd>
      </button>

      {/* Mobile: icon button */}
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={() => setOpen(true)}
        aria-label={t2('search.title')}
      >
        <Search className="h-5 w-5" />
      </Button>
    </>
  );
}
