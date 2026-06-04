import { notFound } from 'next/navigation';
import Link from 'next/link';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getTasksByTopic } from '@/lib/tasks';
import { TaskCard } from '@/components/tasks/TaskCard';

interface Props {
  params: { topicId: string };
}

export function generateStaticParams() {
  return TOPICS.map((t) => ({ topicId: t.id }));
}

export default function TopicTasksPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const tasks = getTasksByTopic(params.topicId);

  return (
    <div className="container py-8 space-y-6">
      <div>
        <Link href="/tasks" className="text-sm text-muted-foreground hover:underline">
          ← Tasks
        </Link>
        <h1 className="text-3xl font-bold mt-2">{topic.label}</h1>
        <p className="text-muted-foreground">{tasks.length} tasks</p>
      </div>
      {tasks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} locale="en" />
          ))}
        </div>
      ) : (
        <p className="text-center text-muted-foreground py-12">
          No tasks for this topic yet.
        </p>
      )}
    </div>
  );
}
