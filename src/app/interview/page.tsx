import type { Metadata } from 'next';
import { getAllQuestions } from '@/lib/questions';
import { getAllTasks } from '@/lib/tasks';
import { InterviewConfig } from './InterviewConfig';

export const metadata: Metadata = { title: 'Mock Interview' };

export default function InterviewPage() {
  const allQuestions = getAllQuestions();
  const allTasks = getAllTasks();

  return <InterviewConfig allQuestions={allQuestions} allTasks={allTasks} />;
}
