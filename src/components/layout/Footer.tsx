'use client';

import { useLocale } from '@/context/LocaleContext';

export function Footer() {
  const { t2 } = useLocale();

  return (
    <footer className="border-t py-6 text-center text-sm text-muted-foreground">
      <p>Full Stack Trainer — {t2('footer.tagline')}</p>
    </footer>
  );
}
