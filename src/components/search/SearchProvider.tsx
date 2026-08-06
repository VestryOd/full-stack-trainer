'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { getTopicById } from '@/constants/topics';
import { getCourseById } from '@/constants/courses';
import type { SearchType, SearchScope } from '@/lib/search/config';
import { SearchDialog } from './SearchDialog';

interface SearchContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const SECTION_TO_TYPE: Record<string, SearchType> = {
  theory: 'theory',
  questions: 'question',
  tasks: 'task',
  courses: 'course',
};

function scopeFromPath(pathname: string): SearchScope {
  const seg = pathname.split('/').filter(Boolean); // e.g. ['questions', 'react']
  const type = SECTION_TO_TYPE[seg[0]] ?? null;
  if (!type) return { type: null, topicId: null, topicLabel: null };
  const topicId = seg[1] ?? null;
  if (!topicId) return { type, topicId: null, topicLabel: null };
  const label = type === 'course' ? getCourseById(topicId)?.label : getTopicById(topicId)?.label;
  return { type, topicId, topicLabel: label ?? topicId };
}

const SearchContext = createContext<SearchContextValue | null>(null);

export function useSearchDialog(): SearchContextValue {
  const ctx = useContext(SearchContext);
  if (!ctx) throw new Error('useSearchDialog must be used within <SearchProvider>');
  return ctx;
}

function isEditableTarget(): boolean {
  const el = document.activeElement as HTMLElement | null;
  if (!el) return false;
  return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable;
}

export function SearchProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // Cmd/Ctrl-K toggles from anywhere.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
        return;
      }
      // "/" opens, but only when not typing in a field (mirrors GitHub/Linear).
      if (e.key === '/' && !open && !isEditableTarget()) {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  return (
    <SearchContext.Provider value={{ open, setOpen }}>
      {children}
      <SearchDialog open={open} onOpenChange={setOpen} scope={scopeFromPath(pathname)} />
    </SearchContext.Provider>
  );
}
