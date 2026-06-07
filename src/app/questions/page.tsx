import { TOPICS } from '@/constants/topics';
import { getQuestionsByTopic } from '@/lib/questions';
import { QuestionsTopicsGrid } from '@/components/questions/QuestionsTopicsGrid';

export default function QuestionsPage() {
  const topicsWithCounts = TOPICS.map((t) => ({
    ...t,
    count: getQuestionsByTopic(t.id).length,
  })).filter((t) => t.count > 0);

  const totalQuestions = topicsWithCounts.reduce((sum, t) => sum + t.count, 0);

  return (
    <div className="container py-8">
      <QuestionsTopicsGrid topicsWithCounts={topicsWithCounts} totalQuestions={totalQuestions} />
    </div>
  );
}
