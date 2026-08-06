'use client';

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import type { Locale } from '@/types';
import { translations } from '@/i18n/translations';

interface LocaleContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (obj: { en: string; ru: string }) => string;
  t2: (key: string) => string;
}

function resolveTranslation(key: string, locale: Locale): string {
  const parts = key.split('.');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let node: any = translations;
  for (const part of parts) {
    node = node?.[part];
  }
  if (node && typeof node === 'object' && (locale in node)) {
    return node[locale];
  }
  return key;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: 'en',
  setLocale: () => {},
  t: (obj) => obj.en,
  t2: (key) => resolveTranslation(key, 'en'),
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('en');
  // `false` on both the server and the first client render → no hydration mismatch.
  // We cover the app with a loader until the stored locale is applied, so the
  // initial `en` → stored-locale swap never flashes on screen.
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('fst-locale') as Locale | null;
      if (stored === 'en' || stored === 'ru') {
        setLocaleState(stored);
      }
    } catch {
      // localStorage unavailable (e.g. private browsing) — keep default locale
    }
    setHydrated(true);
  }, []);

  function setLocale(l: Locale) {
    setLocaleState(l);
    try {
      localStorage.setItem('fst-locale', l);
    } catch {
      // localStorage unavailable — locale won't persist across reloads
    }
  }

  function t(obj: { en: string; ru: string }): string {
    return obj[locale];
  }

  function t2(key: string): string {
    return resolveTranslation(key, locale);
  }

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t, t2 }}>
      {children}
      {!hydrated && (
        <div
          aria-hidden
          className="fixed inset-0 z-[100] flex items-center justify-center bg-background"
        >
          <div className="flex flex-col items-center gap-3">
            <span className="text-2xl font-bold text-primary">FST</span>
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </div>
      )}
    </LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}
