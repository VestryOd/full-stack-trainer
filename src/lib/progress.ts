'use client';

import { useState, useEffect, useCallback } from 'react';

interface QuizHistoryEntry {
  date: string;
  score: number;
  total: number;
  topics: string[];
}

interface ProgressStore {
  reviewedQuestions: string[];
  solvedTasks: string[];
  quizHistory: QuizHistoryEntry[];
}

const STORAGE_KEY = 'fst-progress';

const DEFAULT_STORE: ProgressStore = {
  reviewedQuestions: [],
  solvedTasks: [],
  quizHistory: [],
};

function load(): ProgressStore {
  if (typeof window === 'undefined') return DEFAULT_STORE;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STORE;
    return { ...DEFAULT_STORE, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_STORE;
  }
}

function save(store: ProgressStore): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function useProgress() {
  const [store, setStore] = useState<ProgressStore>(DEFAULT_STORE);

  useEffect(() => {
    setStore(load());
  }, []);

  const markQuestionReviewed = useCallback((id: string) => {
    setStore((prev) => {
      const next = { ...prev, reviewedQuestions: [...new Set([...prev.reviewedQuestions, id])] };
      save(next);
      return next;
    });
  }, []);

  const unmarkQuestionReviewed = useCallback((id: string) => {
    setStore((prev) => {
      const next = { ...prev, reviewedQuestions: prev.reviewedQuestions.filter((q) => q !== id) };
      save(next);
      return next;
    });
  }, []);

  const markTaskSolved = useCallback((id: string) => {
    setStore((prev) => {
      const next = { ...prev, solvedTasks: [...new Set([...prev.solvedTasks, id])] };
      save(next);
      return next;
    });
  }, []);

  const unmarkTaskSolved = useCallback((id: string) => {
    setStore((prev) => {
      const next = { ...prev, solvedTasks: prev.solvedTasks.filter((t) => t !== id) };
      save(next);
      return next;
    });
  }, []);

  const addQuizHistory = useCallback((entry: QuizHistoryEntry) => {
    setStore((prev) => {
      const next = { ...prev, quizHistory: [entry, ...prev.quizHistory].slice(0, 50) };
      save(next);
      return next;
    });
  }, []);

  return {
    store,
    markQuestionReviewed,
    unmarkQuestionReviewed,
    markTaskSolved,
    unmarkTaskSolved,
    addQuizHistory,
  };
}

export function useQuestionReviewed(id: string): [boolean, () => void] {
  const [reviewed, setReviewed] = useState(false);

  useEffect(() => {
    const s = load();
    setReviewed(s.reviewedQuestions.includes(id));
  }, [id]);

  const toggle = useCallback(() => {
    const s = load();
    const wasReviewed = s.reviewedQuestions.includes(id);
    const next: ProgressStore = {
      ...s,
      reviewedQuestions: wasReviewed
        ? s.reviewedQuestions.filter((q) => q !== id)
        : [...s.reviewedQuestions, id],
    };
    save(next);
    setReviewed(!wasReviewed);
  }, [id]);

  return [reviewed, toggle];
}

export function useTaskSolved(id: string): [boolean, () => void] {
  const [solved, setSolved] = useState(false);

  useEffect(() => {
    const s = load();
    setSolved(s.solvedTasks.includes(id));
  }, [id]);

  const toggle = useCallback(() => {
    const s = load();
    const wasSolved = s.solvedTasks.includes(id);
    const next: ProgressStore = {
      ...s,
      solvedTasks: wasSolved
        ? s.solvedTasks.filter((t) => t !== id)
        : [...s.solvedTasks, id],
    };
    save(next);
    setSolved(!wasSolved);
  }, [id]);

  return [solved, toggle];
}

export function getProgressSnapshot(): ProgressStore {
  return load();
}
