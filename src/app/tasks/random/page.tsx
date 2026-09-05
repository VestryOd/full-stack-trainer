import type { Metadata } from 'next';
import { RandomTaskSetClient } from './RandomTaskSetClient';

export const metadata: Metadata = { title: 'Random Tasks' };

export default function RandomTasksPage() {
  return <RandomTaskSetClient />;
}
