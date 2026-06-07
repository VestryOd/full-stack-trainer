'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useLocale } from '@/context/LocaleContext';

export default function NotFound() {
  const { t2 } = useLocale();

  return (
    <div className="container flex flex-col items-center justify-center gap-4 py-24 text-center">
      <p className="text-6xl font-bold text-primary">404</p>
      <h1 className="text-2xl font-semibold">{t2('notFound.title')}</h1>
      <p className="text-muted-foreground max-w-md">{t2('notFound.subtitle')}</p>
      <Button asChild>
        <Link href="/">{t2('notFound.backHome')}</Link>
      </Button>
    </div>
  );
}
