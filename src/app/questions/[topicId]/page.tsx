import { notFound } from 'next/navigation';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getQuestionsByTopic } from '@/lib/questions';
import { renderArticleHtml } from '@/components/theory/ArticleRenderer';
import { TopicQuestionsView } from '@/components/questions/TopicQuestionsView';
import type { QuestionWithAnswerHtml } from '@/components/questions/QuestionCard';

interface Props {
  params: { topicId: string };
}

export function generateStaticParams() {
  return TOPICS.map((t) => ({ topicId: t.id }));
}

export default async function TopicQuestionsPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const questions = getQuestionsByTopic(params.topicId);

  // Pre-render answer markdown to HTML on the server (shiki github-dark), same pipeline as Theory/Tasks
  const questionsWithHtml: QuestionWithAnswerHtml[] = await Promise.all(
    questions.map(async (q) => ({
      ...q,
      answerHtml: {
        en: await renderArticleHtml(q.answer.en),
        ru: await renderArticleHtml(q.answer.ru ?? q.answer.en),
      },
    })),
  );

  return <TopicQuestionsView topic={topic} questions={questionsWithHtml} />;
}
