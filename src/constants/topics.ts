import type { Topic } from '@/types';

export const TOPICS: readonly Topic[] = [
  { id: 'javascript',      label: 'JavaScript',             level: 'deep' },
  { id: 'typescript',      label: 'TypeScript Advanced',    level: 'deep' },
  { id: 'react',            label: 'React',                  level: 'deep' },
  { id: 'state-management', label: 'State Management',      level: 'medium' },
  { id: 'nextjs',           label: 'Next.js',               level: 'deep' },
  { id: 'nodejs',           label: 'Node.js',               level: 'deep' },
  { id: 'aws',              label: 'AWS',                    level: 'deep' },
  { id: 'nestjs',           label: 'Nest.js',               level: 'medium' },
  { id: 'strapi',           label: 'Strapi CMS',            level: 'medium' },
  { id: 'postgresql',       label: 'PostgreSQL',            level: 'medium' },
  { id: 'prisma',           label: 'Prisma ORM',            level: 'medium' },
  { id: 'redis',            label: 'Redis',                  level: 'medium' },
  { id: 'graphql',         label: 'GraphQL',                level: 'medium' },
  { id: 'css-html',        label: 'CSS + HTML Advanced',    level: 'medium' },
  { id: 'web-performance', label: 'Web Performance',        level: 'medium' },
  { id: 'browser-runtime', label: 'Browser / JS Runtime',  level: 'medium' },
  { id: 'http-rest',       label: 'HTTP / REST',            level: 'medium' },
  { id: 'testing',         label: 'Testing',                level: 'medium' },
  { id: 'security',        label: 'Security',               level: 'medium' },
  { id: 'solid-grasp',     label: 'SOLID + GRASP',         level: 'medium' },
  { id: 'oop-patterns',    label: 'OOP Patterns (GoF)',     level: 'medium' },
  { id: 'algorithms',      label: 'Algorithms & DS',        level: 'medium' },
  { id: 'system-design',   label: 'System Design',         level: 'medium' },
  { id: 'architecture',    label: 'Architecture Patterns',  level: 'medium' },
  { id: 'git',             label: 'Git + Git Flow',         level: 'light' },
  { id: 'cicd-devops',    label: 'CI/CD & DevOps',         level: 'deep' },
  { id: 'ci-cd',           label: 'CI/CD',                  level: 'light' },
  { id: 'docker',          label: 'Docker',                 level: 'light' },
  { id: 'bundlers',        label: 'Webpack / Vite',         level: 'light' },
  { id: 'ddd',             label: 'DDD (Basics)',           level: 'light' },
  { id: 'tdd',             label: 'TDD',                    level: 'light' },
  { id: 'event-driven',    label: 'Event-Driven / CQRS',   level: 'light' },
] as const;

export const TOPIC_IDS = TOPICS.map((t) => t.id);

export function getTopicById(id: string): Topic | undefined {
  return TOPICS.find((t) => t.id === id);
}
