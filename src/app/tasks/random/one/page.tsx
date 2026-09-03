import type { Metadata } from 'next';
import { getTaskIndex } from '@/lib/tasks';
import { RandomOneClient } from './RandomOneClient';

export const metadata: Metadata = { title: 'Random Task' };

export default function RandomOneTaskPage() {
  return <RandomOneClient index={getTaskIndex()} />;
}
