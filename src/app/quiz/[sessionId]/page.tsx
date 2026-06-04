import { TOPICS } from '@/constants/topics';
import { QuizSession } from './QuizSession';

interface Props {
  params: { sessionId: string };
}

export function generateStaticParams() {
  const counts = [5, 10, 20];
  const params: { sessionId: string }[] = [];
  for (const topic of TOPICS) {
    for (const count of counts) {
      params.push({ sessionId: `${topic.id}-${count}` });
    }
  }
  return params;
}

export default function QuizSessionPage({ params }: Props) {
  return <QuizSession sessionId={params.sessionId} />;
}
