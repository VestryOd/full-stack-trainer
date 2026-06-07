import { getAllQuestions } from './questions';
import type { Question, QuizQuestion } from '@/types';

function extractShortAnswer(markdown: string | undefined | null): string {
  if (!markdown) return '';
  const cleaned = markdown
    .replace(/```[\s\S]*?```/g, '')
    .replace(/^#{1,6}\s+.+$/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^\s*[-*+\d]+\.?\s+/gm, '')
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  return cleaned.length > 200 ? cleaned.slice(0, 197) + '…' : cleaned;
}

function shuffled<T>(arr: T[]): T[] {
  return [...arr].sort(() => Math.random() - 0.5);
}

function buildQuizQuestions(selected: Question[], allPool: Question[]): QuizQuestion[] {
  return selected.map((q) => {
    const answerEn = q.answer?.en;
    const answerRu = q.answer?.ru ?? q.answer?.en;
    const correctEn = extractShortAnswer(answerEn);
    const correctRu = extractShortAnswer(answerRu);

    const otherPool = allPool.filter((other) => other.id !== q.id && other.answer?.en);
    const wrongPicks = shuffled(otherPool).slice(0, 3);

    const optionsEn = [correctEn, ...wrongPicks.map((w) => extractShortAnswer(w.answer?.en))];
    const optionsRu = [correctRu, ...wrongPicks.map((w) => extractShortAnswer(w.answer?.ru ?? w.answer?.en))];

    // Same permutation applied to both locales
    const order = shuffled([0, 1, 2, 3]);
    const correctIndex = order.indexOf(0);

    return {
      id: q.id,
      topicId: q.topicId,
      question: {
        en: q.question?.en ?? '',
        ru: q.question?.ru ?? q.question?.en ?? '',
      },
      options: {
        en: order.map((i) => optionsEn[i]),
        ru: order.map((i) => optionsRu[i]),
      },
      correctIndex,
      explanation: {
        en: correctEn,
        ru: correctRu,
      },
    };
  });
}

export function getQuizForSession(topicId: string, count: number): QuizQuestion[] {
  const allPool = getAllQuestions();
  const topicPool = allPool.filter((q) => q.topicId === topicId && q.answer?.en);

  const selected = shuffled(topicPool).slice(0, count);
  return buildQuizQuestions(selected, allPool);
}
