import type { QuizQuestion } from '@/types';

export function fisherYates<T>(arr: T[]): T[] {
  const result = [...arr];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

export function shuffleOptions(question: QuizQuestion): QuizQuestion {
  const len = question.options.en.length;
  const perm = Array.from({ length: len }, (_, i) => i);
  for (let i = len - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [perm[i], perm[j]] = [perm[j], perm[i]];
  }
  return {
    ...question,
    options: {
      en: perm.map((i) => question.options.en[i]),
      ru: perm.map((i) => (question.options.ru ?? question.options.en)[i]),
    },
    correctIndex: perm.indexOf(question.correctIndex),
  };
}

export function dedupeById(questions: QuizQuestion[]): QuizQuestion[] {
  const seen = new Set<string>();
  return questions.filter((q) => {
    if (seen.has(q.id)) return false;
    seen.add(q.id);
    return true;
  });
}
