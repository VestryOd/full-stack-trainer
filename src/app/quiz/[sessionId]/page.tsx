import type { Metadata } from 'next';
import { getTopicById } from '@/constants/topics';
import { getAvailableQuizTopics, getQuizQuestions, getTopicQuestionCount } from '@/lib/quiz';
import { renderArticleHtml } from '@/components/theory/ArticleRenderer';
import type { QuizQuestionWithHtml } from '@/components/quiz/QuizCard';
import { QuizSession } from './QuizSession';

interface Props {
  params: { sessionId: string };
}

function parseSessionId(sessionId: string): { topicId: string; count: number } {
  const parts = sessionId.split('-');
  const count = parseInt(parts[parts.length - 1], 10);
  const topicId = parts.slice(0, -1).join('-');
  return { topicId, count: isNaN(count) ? 10 : count };
}

export function generateMetadata({ params }: Props): Metadata {
  const { topicId } = parseSessionId(params.sessionId);
  const topic = getTopicById(topicId);
  return { title: topic ? `${topic.label} Quiz` : 'Quiz' };
}

export function generateStaticParams() {
  const params: { sessionId: string }[] = [];
  for (const topicId of getAvailableQuizTopics()) {
    const total = getTopicQuestionCount(topicId);
    for (let count = 1; count <= total; count++) {
      params.push({ sessionId: `${topicId}-${count}` });
    }
  }
  return params;
}

export default async function QuizSessionPage({ params }: Props) {
  const { topicId, count } = parseSessionId(params.sessionId);
  const questions = getQuizQuestions([topicId], count);

  // Pre-render question markdown to HTML on the server (shiki github-dark), same pipeline as Theory/Questions
  const questionsWithHtml: QuizQuestionWithHtml[] = await Promise.all(
    questions.map(async (q) => ({
      ...q,
      questionHtml: {
        en: await renderArticleHtml(q.question.en),
        ru: await renderArticleHtml(q.question.ru ?? q.question.en),
      },
    })),
  );

  return <QuizSession initialQuestions={questionsWithHtml} />;
}
