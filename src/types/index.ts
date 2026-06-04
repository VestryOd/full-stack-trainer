export type Locale = 'en' | 'ru';

export type TopicLevel = 'deep' | 'medium' | 'light';

export interface Topic {
  id: string;
  label: string;
  level: TopicLevel;
}

export interface TheoryArticle {
  topicId: string;
  slug: string;
  title: string;
  content: string;
  locale: Locale;
}

export type QuestionDifficulty = 'junior' | 'middle' | 'senior' | 'advanced';

export interface Question {
  id: string;
  topicId: string;
  difficulty: QuestionDifficulty;
  question: { en: string; ru: string };
  answer: { en: string; ru: string };
  tags: string[];
}

export type TaskDifficulty = 'easy' | 'medium' | 'hard';

export interface Task {
  id: string;
  topicId: string;
  difficulty: TaskDifficulty;
  title: { en: string; ru: string };
  description: { en: string; ru: string };
  starterCode?: string;
  solution: string;
  solutionExplanation: { en: string; ru: string };
  tags: string[];
}

export interface QuizQuestion {
  id: string;
  topicId: string;
  question: { en: string; ru: string };
  options: { en: string[]; ru: string[] };
  correctIndex: number;
  explanation: { en: string; ru: string };
}
