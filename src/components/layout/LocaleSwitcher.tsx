'use client';

import { useLocale } from '@/context/LocaleContext';
import { Button } from '@/components/ui/button';

export function LocaleSwitcher() {
  const { locale, setLocale } = useLocale();

  return (
    <div className="flex items-center gap-1">
      <Button
        variant={locale === 'en' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => setLocale('en')}
        className="h-7 px-2 text-xs"
      >
        EN
      </Button>
      <Button
        variant={locale === 'ru' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => setLocale('ru')}
        className="h-7 px-2 text-xs"
      >
        RU
      </Button>
    </div>
  );
}
