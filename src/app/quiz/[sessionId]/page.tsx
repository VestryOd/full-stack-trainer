import { getAvailableQuizTopics, getQuizQuestions } from '@/lib/quiz';
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

export function generateStaticParams() {
  const counts = [5, 10, 20];
  const params: { sessionId: string }[] = [];
  for (const topicId of getAvailableQuizTopics()) {
    for (const count of counts) {
      params.push({ sessionId: `${topicId}-${count}` });
    }
  }
  return params;
}

export default function QuizSessionPage({ params }: Props) {
  const { topicId, count } = parseSessionId(params.sessionId);
  const questions = getQuizQuestions([topicId], count);

  return <QuizSession initialQuestions={questions} />;
}
