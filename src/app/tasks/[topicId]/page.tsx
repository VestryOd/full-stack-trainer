import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getTasksByTopic } from '@/lib/tasks';
import { TopicTasksView } from '@/components/tasks/TopicTasksView';

interface Props {
  params: { topicId: string };
}

export function generateStaticParams() {
  return TOPICS.map((t) => ({ topicId: t.id }));
}

export function generateMetadata({ params }: Props): Metadata {
  const topic = getTopicById(params.topicId);
  if (!topic) return {};
  return { title: `${topic.label} Coding Tasks` };
}

export default function TopicTasksPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const tasks = getTasksByTopic(params.topicId);

  return <TopicTasksView topic={topic} tasks={tasks} />;
}
