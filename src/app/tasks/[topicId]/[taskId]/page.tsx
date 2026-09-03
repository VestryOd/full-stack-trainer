import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getTasksByTopic, getTaskById } from '@/lib/tasks';
import { renderArticleHtml } from '@/components/theory/ArticleRenderer';
import { CodeBlock } from '@/components/tasks/CodeBlock';
import { TaskView } from '@/components/tasks/TaskView';

interface Props {
  params: { topicId: string; taskId: string };
}

/**
 * A task carries no language of its own, and these three topics are not TypeScript:
 * all 35 `css-html` tasks are HTML with embedded CSS, and `react`/`testing` hold 32
 * JSX blocks between them. Under the TypeScript grammar an HTML tag name gets no
 * colour at all and `<`/`>` render as comparison operators, while a closing `</span>`
 * is tokenised as a regex.
 *
 * `tsx` is a superset of `ts`, so it also renders the JSX-free tasks in those two
 * topics correctly — verified identical output on `react-t-20`.
 */
const CODE_LANG: Record<string, string> = {
  'css-html': 'html',
  react: 'tsx',
  testing: 'tsx',
};

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

export function generateMetadata({ params }: Props): Metadata {
  const task = getTaskById(params.topicId, params.taskId);
  if (!task) return {};
  return { title: task.title.en };
}

export default async function TaskPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const task = getTaskById(params.topicId, params.taskId);
  if (!task) notFound();

  const codeLang = CODE_LANG[task.topicId] ?? 'typescript';

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
      starterCodeBlock={task.starterCode ? <CodeBlock code={task.starterCode} lang={codeLang} /> : null}
      solutionCodeBlock={<CodeBlock code={task.solution} lang={codeLang} />}
      topicTaskIds={getTasksByTopic(params.topicId).map((t) => t.id)}
    />
  );
}
