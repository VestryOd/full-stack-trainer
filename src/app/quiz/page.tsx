import { TOPICS } from '@/constants/topics';
import { getAvailableQuizTopics } from '@/lib/quiz';
import { QuizTopicsGrid } from '@/components/quiz/QuizTopicsGrid';

export default function QuizPage() {
  const quizTopicIds = new Set(getAvailableQuizTopics());
  const topicsWithQuiz = TOPICS.filter((topic) => quizTopicIds.has(topic.id));

  return <QuizTopicsGrid topics={topicsWithQuiz} />;
}
