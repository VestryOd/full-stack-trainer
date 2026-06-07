import { notFound } from 'next/navigation';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getTasksByTopic, getTaskById } from '@/lib/tasks';
import { renderArticleHtml } from '@/components/theory/ArticleRenderer';
import { CodeBlock } from '@/components/tasks/CodeBlock';
import { TaskView } from '@/components/tasks/TaskView';

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

export default async function TaskPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const task = getTaskById(params.topicId, params.taskId);
  if (!task) notFound();

  // Pre-render description/explanation markdown to HTML on the server (shiki github-dark)
  const [descriptionEn, descriptionRu, explanationEn, explanationRu] = await Promise.all([
    renderArticleHtml(task.description.en),
    renderArticleHtml(task.description.ru),
    renderArticleHtml(task.solutionExplanation.en),
    renderArticleHtml(task.solutionExplanation.ru),
  ]);

  return (
    <TaskView
      topic={topic}
      task={task}
      descriptionHtml={{ en: descriptionEn, ru: descriptionRu }}
      solutionExplanationHtml={{ en: explanationEn, ru: explanationRu }}
      starterCodeBlock={task.starterCode ? <CodeBlock code={task.starterCode} lang="typescript" /> : null}
      solutionCodeBlock={<CodeBlock code={task.solution} lang="typescript" />}
    />
  );
}
