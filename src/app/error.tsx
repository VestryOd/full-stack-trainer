'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useLocale } from '@/context/LocaleContext';

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  const { t2 } = useLocale();

  return (
    <div className="container flex flex-col items-center justify-center gap-4 py-24 text-center">
      <h1 className="text-2xl font-semibold">{t2('error.title')}</h1>
      <p className="text-muted-foreground max-w-md">{t2('error.subtitle')}</p>
      <p className="font-mono text-xs text-muted-foreground/70 max-w-md break-words">{error.message}</p>
      <div className="flex gap-3">
        <Button onClick={reset}>{t2('error.retry')}</Button>
        <Button asChild variant="outline">
          <Link href="/">{t2('error.backHome')}</Link>
        </Button>
      </div>
    </div>
  );
}
