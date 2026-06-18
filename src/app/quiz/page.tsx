import type { Metadata } from 'next';
import { TOPICS } from '@/constants/topics';
import { getAvailableQuizTopics, getTopicQuestionCount } from '@/lib/quiz';
import { QuizTopicsGrid } from '@/components/quiz/QuizTopicsGrid';

export const metadata: Metadata = { title: 'Quiz' };

export default function QuizPage() {
  const quizTopicIds = new Set(getAvailableQuizTopics());
  const topicsWithQuiz = TOPICS.filter((topic) => quizTopicIds.has(topic.id));
  const questionCounts = Object.fromEntries(
    topicsWithQuiz.map((topic) => [topic.id, getTopicQuestionCount(topic.id)]),
  );
  return <QuizTopicsGrid topics={topicsWithQuiz} questionCounts={questionCounts} />;
}
