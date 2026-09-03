'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Shuffle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useLocale } from '@/context/LocaleContext';
import { clearPlaylist, href, loadPlaylist, type TaskPlaylist } from '@/lib/tasks-random';

/**
 * Shown only while a random set is running and the open task belongs to it. The set
 * lives in sessionStorage, so it survives navigation between task pages but not a
 * new tab — which is the behaviour the quiz already has.
 */
export function TaskSetBar({ taskId }: { taskId: string }) {
  const { t2 } = useLocale();
  const router = useRouter();
  const [playlist, setPlaylist] = useState<TaskPlaylist | null>(null);

  // sessionStorage is unavailable during the static render, so this runs after mount
  useEffect(() => setPlaylist(loadPlaylist()), []);

  if (!playlist) return null;
  const position = playlist.refs.findIndex((ref) => ref.id === taskId);
  if (position === -1) return null;

  const last = position === playlist.refs.length - 1;

  function exit() {
    clearPlaylist();
    setPlaylist(null);
    router.push('/tasks');
  }

  return (
    <div className="rounded-md border border-primary/30 bg-primary/5 px-4 py-3 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <Badge variant="outline" className="gap-1.5 border-primary/30 text-primary">
          <Shuffle className="h-3 w-3" />
          {t2('tasks.setBadge')}
        </Badge>
        <span className="text-sm text-muted-foreground tabular-nums">
          {position + 1} / {playlist.refs.length}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={position === 0}
          onClick={() => router.push(href(playlist.refs[position - 1]))}
        >
          {t2('tasks.prev')}
        </Button>
        <Button
          size="sm"
          disabled={last}
          onClick={() => router.push(href(playlist.refs[position + 1]))}
        >
          {t2('tasks.next')}
        </Button>
        <Button variant="ghost" size="sm" className="ml-auto" onClick={exit}>
          {t2('tasks.exitSet')}
        </Button>
      </div>
      {last && <p className="text-sm text-muted-foreground">{t2('tasks.setDone')}</p>}
    </div>
  );
}
