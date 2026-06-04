import { notFound } from 'next/navigation';
import Link from 'next/link';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getTasksByTopic, getTaskById } from '@/lib/tasks';
import { CodeBlock } from '@/components/tasks/CodeBlock';
import { SolutionSpoiler } from '@/components/tasks/SolutionSpoiler';
import { Badge } from '@/components/ui/badge';

interface Props {
  params: { topicId: string; taskId: string };
}

export async function generateStaticParams() {
  const params: { topicId: string; taskId: string }[] = [];
  for (const topic of TOPICS) {
    const tasks = getTasksByTopic(topic.id);
    for (const task of tasks) {
      params.push({ topicId: topic.id, taskId: task.id });
    }
  }
  return params;
}

const DIFFICULTY_COLORS = {
  easy:   'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  hard:   'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

export default async function TaskPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const task = getTaskById(params.topicId, params.taskId);
  if (!task) notFound();

  return (
    <div className="container py-8 max-w-4xl space-y-6">
      <div>
        <div className="flex gap-2 text-sm text-muted-foreground">
          <Link href="/tasks" className="hover:underline">Tasks</Link>
          <span>/</span>
          <Link href={`/tasks/${topic.id}`} className="hover:underline">{topic.label}</Link>
        </div>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-3xl font-bold">{task.title.en}</h1>
          <Badge variant="outline" className={DIFFICULTY_COLORS[task.difficulty]}>
            {task.difficulty}
          </Badge>
        </div>
      </div>

      <div className="prose prose-slate dark:prose-invert max-w-none">
        <p>{task.description.en}</p>
      </div>

      {task.starterCode && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Starter Code</h2>
          <CodeBlock code={task.starterCode} lang="typescript" />
        </div>
      )}

      <SolutionSpoiler>
        <div className="space-y-4">
          <CodeBlock code={task.solution} lang="typescript" />
          <div className="prose prose-slate dark:prose-invert max-w-none text-sm">
            <p>{task.solutionExplanation.en}</p>
          </div>
        </div>
      </SolutionSpoiler>

      <div className="flex flex-wrap gap-1">
        {task.tags.map((tag) => (
          <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
        ))}
      </div>
    </div>
  );
}
