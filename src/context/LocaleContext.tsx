'use client';

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
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

  useEffect(() => {
    const stored = localStorage.getItem('fst-locale') as Locale | null;
    if (stored === 'en' || stored === 'ru') {
      setLocaleState(stored);
    }
  }, []);

  function setLocale(l: Locale) {
    setLocaleState(l);
    localStorage.setItem('fst-locale', l);
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
    </LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}
