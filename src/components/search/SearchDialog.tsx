'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useRouter } from 'next/navigation';
import { Search, CornerDownLeft, Loader2, FileText, HelpCircle, Code2, GraduationCap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLocale } from '@/context/LocaleContext';
import { useSearchIndex, type SearchOutcome } from '@/lib/search/useSearchIndex';
import { SEARCH_TYPE_LABEL_KEY, type SearchDisplayDoc, type SearchType } from '@/lib/search/config';

const EMPTY: SearchOutcome = { groups: [], flat: [], total: 0, truncated: false };

const TYPE_ICON: Record<SearchType, typeof FileText> = {
  theory: FileText,
  question: HelpCircle,
  task: Code2,
  course: GraduationCap,
};

const DIFFICULTY_CLASS: Record<string, string> = {
  junior: 'text-green-500',
  easy: 'text-green-500',
  middle: 'text-yellow-500',
  medium: 'text-yellow-500',
  senior: 'text-orange-500',
  hard: 'text-red-500',
  advanced: 'text-red-500',
};

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

interface SearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SearchDialog({ open, onOpenChange }: SearchDialogProps) {
  const { locale, t2 } = useLocale();
  const router = useRouter();
  const { status, search } = useSearchIndex(locale, open);

  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // The dialog stays mounted (only Radix's Content unmounts), so reset when closed.
  useEffect(() => {
    if (!open) {
      setQuery('');
      setActive(0);
    }
  }, [open]);

  const results = useMemo<SearchOutcome>(() => {
    if (!open || status !== 'ready') return EMPTY;
    return search(query);
  }, [open, status, query, search]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  // Keep the highlighted row in view during keyboard navigation.
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  const highlight = useMemo(() => {
    const terms = query
      .trim()
      .toLowerCase()
      .split(/\s+/)
      .filter((t) => t.length >= 2)
      .map(escapeRegExp);
    if (!terms.length) return (text: string) => text as React.ReactNode;
    const re = new RegExp(`(${terms.join('|')})`, 'ig');
    return (text: string): React.ReactNode =>
      text.split(re).map((part, i) =>
        i % 2 === 1 ? (
          <mark key={i} className="bg-primary/20 text-foreground rounded-[2px]">
            {part}
          </mark>
        ) : (
          part
        ),
      );
  }, [query]);

  const select = useCallback(
    (doc: SearchDisplayDoc | undefined) => {
      if (!doc) return;
      onOpenChange(false);
      router.push(doc.url);
    },
    [onOpenChange, router],
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const n = results.flat.length;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActive((a) => (n ? (a + 1) % n : 0));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActive((a) => (n ? (a - 1 + n) % n : 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        select(results.flat[active]);
      }
    },
    [results.flat, active, select],
  );

  const trimmed = query.trim();
  const showEmpty = status === 'ready' && trimmed.length >= 2 && results.total === 0;

  // Flatten index bookkeeping so each row gets a global index for keyboard nav.
  let flatIdx = -1;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          onKeyDown={onKeyDown}
          className="fixed left-1/2 top-[12vh] z-50 w-[92vw] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-popover shadow-2xl outline-none focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:slide-in-from-top-2"
        >
          <Dialog.Title className="sr-only">{t2('search.title')}</Dialog.Title>
          <Dialog.Description className="sr-only">{t2('search.placeholder')}</Dialog.Description>

          {/* Search input */}
          <div className="flex items-center gap-2 border-b border-border px-4">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t2('search.placeholder')}
              className="h-12 w-full bg-transparent text-sm outline-none focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground"
              aria-label={t2('search.placeholder')}
            />
            {status === 'loading' && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />}
          </div>

          {/* Results */}
          <div ref={listRef} className="max-h-[60vh] overflow-y-auto overscroll-contain py-2">
            {status === 'error' && (
              <p className="px-4 py-6 text-center text-sm text-muted-foreground">{t2('search.error')}</p>
            )}

            {status !== 'error' && trimmed.length < 2 && (
              <p className="px-4 py-6 text-center text-sm text-muted-foreground">{t2('search.hintType')}</p>
            )}

            {showEmpty && (
              <p className="px-4 py-6 text-center text-sm text-muted-foreground">
                {t2('search.empty')} “{trimmed}”
              </p>
            )}

            {results.groups.map((grp) => {
              const Icon = TYPE_ICON[grp.type];
              return (
                <div key={grp.type} className="mb-1">
                  <div className="px-4 pb-1 pt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {t2(SEARCH_TYPE_LABEL_KEY[grp.type])}
                  </div>
                  {grp.hits.map((doc) => {
                    flatIdx += 1;
                    const idx = flatIdx;
                    const isActive = idx === active;
                    return (
                      <button
                        key={doc.id}
                        data-idx={idx}
                        onMouseMove={() => setActive(idx)}
                        onClick={() => select(doc)}
                        className={cn(
                          'flex w-full items-start gap-3 px-4 py-2 text-left transition-colors',
                          isActive ? 'bg-accent' : 'hover:bg-accent/50',
                        )}
                      >
                        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium text-foreground">
                              {highlight(doc.title)}
                            </span>
                            {doc.difficulty && (
                              <span
                                className={cn(
                                  'shrink-0 text-[10px] font-mono uppercase',
                                  DIFFICULTY_CLASS[doc.difficulty] ?? 'text-muted-foreground',
                                )}
                              >
                                {doc.difficulty}
                              </span>
                            )}
                          </span>
                          <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
                            <span className="text-foreground/70">{doc.topicLabel}</span>
                            {doc.snippet ? <> — {highlight(doc.snippet)}</> : null}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              );
            })}

            {results.truncated && (
              <p className="px-4 py-2 text-center text-xs text-muted-foreground">{t2('search.refine')}</p>
            )}
          </div>

          {/* Footer hints */}
          <div className="flex items-center justify-between border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <CornerDownLeft className="h-3 w-3" /> {t2('search.hintEnter')}
            </span>
            <span className="hidden sm:inline">↑↓ {t2('search.hintNav')} · Esc</span>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
