'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale } from '@/context/LocaleContext';
import { href, pickRandom, type TaskRef } from '@/lib/tasks-random';

/**
 * «One random task, from anywhere.» This route exists so that the full task index
 * is shipped once, here, instead of being embedded in all 243 task pages. Picking a
 * task *within* a topic needs no index and happens inline on the task page itself.
 */
export function RandomOneClient({ index }: { index: TaskRef[] }) {
  const { t2 } = useLocale();
  const router = useRouter();

  useEffect(() => {
    const ref = pickRandom(index);
    // replace: this route is a hop, it should not sit in history behind the task
    router.replace(ref ? href(ref) : '/tasks');
  }, [index, router]);

  return (
    <div className="container max-w-2xl text-center py-24">
      <p className="text-muted-foreground">{t2('tasks.picking')}</p>
    </div>
  );
}
