import { notFound } from 'next/navigation';
import Link from 'next/link';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getQuestionsByTopic } from '@/lib/questions';
import { QuestionList } from '@/components/questions/QuestionList';

interface Props {
  params: { topicId: string };
}

export function generateStaticParams() {
  return TOPICS.map((t) => ({ topicId: t.id }));
}

export default function TopicQuestionsPage({ params }: Props) {
  const topic = getTopicById(params.topicId);
  if (!topic) notFound();

  const questions = getQuestionsByTopic(params.topicId);

  return (
    <div className="container py-8 space-y-6">
      <div>
        <Link href="/questions" className="text-sm text-muted-foreground hover:underline">
          ← Questions
        </Link>
        <h1 className="text-3xl font-bold mt-2">{topic.label}</h1>
        <p className="text-muted-foreground">{questions.length} questions</p>
      </div>
      <QuestionList questions={questions} />
    </div>
  );
}
