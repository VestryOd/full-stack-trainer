import { notFound } from 'next/navigation';
import Link from 'next/link';
import { TOPICS, getTopicById } from '@/constants/topics';
import { getQuestionsByTopic } from '@/lib/questions';
import { renderArticleHtml } from '@/components/theory/ArticleRenderer';
import { QuestionFilters } from '@/components/questions/QuestionFilters';
import type { QuestionWithAnswerHtml } from '@/components/questions/QuestionCard';
import { ChevronRight } from 'lucide-react';

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

  return (
    <div className="container py-8 space-y-6 max-w-4xl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
        <Link href="/questions" className="hover:text-foreground transition-colors">Questions</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">{topic.label}</span>
      </nav>

      <div>
        <h1 className="text-2xl font-mono font-semibold">{topic.label}</h1>
        <p className="text-muted-foreground text-sm mt-1">{questions.length} questions</p>
      </div>

      {questions.length > 0 ? (
        <QuestionFilters questions={questionsWithHtml} topicLabel={topic.label} />
      ) : (
        <p className="text-center text-muted-foreground py-12 text-sm">
          No questions yet for this topic.
        </p>
      )}
    </div>
  );
}
