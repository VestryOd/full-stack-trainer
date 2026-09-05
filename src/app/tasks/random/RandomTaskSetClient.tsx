'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useLocale } from '@/context/LocaleContext';
import { href, loadPlaylist } from '@/lib/tasks-random';

/**
 * Entry point of a random set: reads the playlist the Tasks page stored and hands
 * off to the first task's own page. Nothing is rendered here for more than a frame,
 * because the task pages already exist and render their code on the server.
 */
export function RandomTaskSetClient() {
  const { t2 } = useLocale();
  const router = useRouter();
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const playlist = loadPlaylist();
    if (!playlist) {
      setMissing(true);
      return;
    }
    // replace, not push: the set entry should not sit in history behind the task
    router.replace(href(playlist.refs[0]));
  }, [router]);

  if (missing) {
    return (
      <div className="container py-8 max-w-2xl text-center space-y-4">
        <p className="text-muted-foreground">{t2('tasks.randomNoSet')}</p>
        <Button asChild>
          <Link href="/tasks">{t2('tasks.title')}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="container max-w-2xl text-center py-24">
      <p className="text-muted-foreground">{t2('tasks.picking')}</p>
    </div>
  );
}
