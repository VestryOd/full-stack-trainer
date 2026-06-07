import type { Metadata } from 'next';
import { TOPICS } from '@/constants/topics';
import { getAllTasks } from '@/lib/tasks';
import { TasksTopicsGrid } from '@/components/tasks/TasksTopicsGrid';

export const metadata: Metadata = { title: 'Coding Tasks' };

export default function TasksPage() {
  const allTasks = getAllTasks();

  const topicsWithTasks = TOPICS.filter((topic) =>
    allTasks.some((t) => t.topicId === topic.id),
  ).map((topic) => ({
    ...topic,
    count: allTasks.filter((t) => t.topicId === topic.id).length,
  }));

  return (
    <div className="container py-8">
      <TasksTopicsGrid topicsWithTasks={topicsWithTasks} totalTasks={allTasks.length} />
    </div>
  );
}
