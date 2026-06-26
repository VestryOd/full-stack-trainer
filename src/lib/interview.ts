import type { Question, Task, QuestionDifficulty } from '@/types';

export const TIMING = {
  questionMinutes: { junior: 2, middle: 2.5, senior: 3, advanced: 3.5 } as const,
  taskMinutes: { easy: 5, medium: 12, hard: 15 } as const,
} as const;

// Fraction of total interview time allocated to coding tasks
export const TASK_TIME_RATIOS: Record<60 | 90 | 120, number> = {
  60: 0.22,
  90: 0.30,
  120: 0.37,
};

// Maximum number of tasks to include
export const TASK_MAX_COUNTS: Record<60 | 90 | 120, number> = {
  60: 1,
  90: 2,
  120: 3,
};

export const DURATION_PRESETS = [60, 90, 120] as const;
export type DurationPreset = typeof DURATION_PRESETS[number];

// Question difficulty band distribution (shares must sum to 1.0)
export const QUESTION_BANDS: Array<{ difficulty: QuestionDifficulty; share: number }> = [
  { difficulty: 'junior',   share: 0.15 },
  { difficulty: 'middle',   share: 0.35 },
  { difficulty: 'senior',   share: 0.35 },
  { difficulty: 'advanced', share: 0.15 },
];

export interface InterviewItem {
  type: 'question' | 'task';
  topicId: string;
  data: Question | Task;
  estimatedMinutes: number;
}

export interface InterviewPlan {
  totalMinutes: number;
  estimatedMinutes: number;
  sequence: InterviewItem[];
}

export interface BuildPlanOptions {
  scope: 'full' | 'custom';
  questionTopicIds?: string[];
  taskTopicIds?: string[];
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function buildInterviewPlan(
  durationMinutes: number,
  options: BuildPlanOptions,
  allQuestions: Question[],
  allTasks: Task[],
): InterviewPlan {
  const { scope, questionTopicIds, taskTopicIds } = options;

  const questionPool =
    scope === 'custom' && questionTopicIds?.length
      ? allQuestions.filter((q) => questionTopicIds.includes(q.topicId))
      : allQuestions;

  const taskPool =
    scope === 'custom' && taskTopicIds?.length
      ? allTasks.filter((t) => taskTopicIds.includes(t.topicId))
      : allTasks;

  const preset = durationMinutes as 60 | 90 | 120;
  const taskBudget = Math.round(durationMinutes * (TASK_TIME_RATIOS[preset] ?? 0.30));
  const maxTasks = TASK_MAX_COUNTS[preset] ?? 2;

  // Select tasks: prefer easy → medium → hard, stop at budget or max count
  const selectedTasks: InterviewItem[] = [];
  let usedTaskMinutes = 0;

  for (const diff of ['easy', 'medium', 'hard'] as const) {
    if (selectedTasks.length >= maxTasks) break;
    for (const task of shuffle(taskPool.filter((t) => t.difficulty === diff))) {
      if (selectedTasks.length >= maxTasks) break;
      const mins = TIMING.taskMinutes[diff];
      if (usedTaskMinutes + mins > taskBudget) continue;
      selectedTasks.push({ type: 'task', topicId: task.topicId, data: task, estimatedMinutes: mins });
      usedTaskMinutes += mins;
    }
  }

  // Give unused task budget back to questions
  const questionBudget = durationMinutes - usedTaskMinutes;

  // Select questions by difficulty band
  const usedIds = new Set<string>();
  const selectedQuestions: InterviewItem[] = [];
  let usedQuestionMinutes = 0;

  for (const band of QUESTION_BANDS) {
    const bandBudget = questionBudget * band.share;
    let bandUsed = 0;
    for (const q of shuffle(questionPool.filter((q) => q.difficulty === band.difficulty))) {
      if (usedIds.has(q.id)) continue;
      if (bandUsed >= bandBudget) break;
      if (usedQuestionMinutes >= questionBudget) break;
      const mins = TIMING.questionMinutes[band.difficulty];
      usedIds.add(q.id);
      selectedQuestions.push({ type: 'question', topicId: q.topicId, data: q, estimatedMinutes: mins });
      bandUsed += mins;
      usedQuestionMinutes += mins;
    }
  }

  return {
    totalMinutes: durationMinutes,
    estimatedMinutes: Math.round(usedQuestionMinutes + usedTaskMinutes),
    sequence: [...selectedQuestions, ...selectedTasks],
  };
}
