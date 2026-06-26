import type { Metadata } from 'next';
import { TOPICS } from '@/constants/topics';
import { getAllQuizQuestionsPerTopic } from '@/lib/quiz';
import { RandomQuizClient } from './RandomQuizClient';

export const metadata: Metadata = { title: 'Random Quiz' };

export default function RandomQuizPage() {
  const allQuestionsPerTopic = getAllQuizQuestionsPerTopic();
  const topicLabels = Object.fromEntries(TOPICS.map((t) => [t.id, t.label]));
  return (
    <RandomQuizClient
      allQuestionsPerTopic={allQuestionsPerTopic}
      topicLabels={topicLabels}
    />
  );
}
