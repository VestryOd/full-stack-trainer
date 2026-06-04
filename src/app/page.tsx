import Link from 'next/link';
import { TOPICS } from '@/constants/topics';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

const SECTIONS = [
  {
    href: '/theory',
    title: 'Theory',
    description: 'In-depth articles on each topic with code examples.',
    icon: '📖',
  },
  {
    href: '/questions',
    title: 'Questions',
    description: 'Interview questions with hidden answers — Junior to Advanced.',
    icon: '❓',
  },
  {
    href: '/quiz',
    title: 'Quiz',
    description: 'Test yourself with multiple-choice quizzes and instant feedback.',
    icon: '🧠',
  },
  {
    href: '/tasks',
    title: 'Tasks',
    description: 'Coding challenges with starter code and hidden solutions.',
    icon: '💻',
  },
] as const;

const LEVEL_COLORS = {
  deep:   'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  medium: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  light:  'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
};

export default function HomePage() {
  return (
    <div className="container py-10 space-y-12">
      <section className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">Full Stack Trainer</h1>
        <p className="text-muted-foreground text-lg max-w-xl mx-auto">
          Structured interview preparation for senior fullstack developers. Theory, questions, quizzes, and coding tasks — all in one place.
        </p>
        <div className="flex justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/theory">Start with Theory</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/quiz">Take a Quiz</Link>
          </Button>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-6">Sections</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {SECTIONS.map((s) => (
            <Link key={s.href} href={s.href}>
              <Card className="h-full transition-colors hover:bg-accent cursor-pointer">
                <CardHeader>
                  <div className="text-3xl mb-2">{s.icon}</div>
                  <CardTitle>{s.title}</CardTitle>
                  <CardDescription>{s.description}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-6">Topics ({TOPICS.length})</h2>
        <div className="flex flex-wrap gap-2">
          {TOPICS.map((topic) => (
            <Link key={topic.id} href={`/theory/${topic.id}`}>
              <Badge
                variant="outline"
                className={`cursor-pointer hover:opacity-80 ${LEVEL_COLORS[topic.level]}`}
              >
                {topic.label}
              </Badge>
            </Link>
          ))}
        </div>
      </section>

      <section className="border rounded-lg p-6 bg-muted/30">
        <h2 className="text-xl font-semibold mb-3">Coverage Levels</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <Badge className={LEVEL_COLORS.deep}>Deep</Badge>
            <p className="mt-2 text-muted-foreground">
              {TOPICS.filter((t) => t.level === 'deep').length} topics — comprehensive coverage with advanced questions
            </p>
          </div>
          <div>
            <Badge className={LEVEL_COLORS.medium}>Medium</Badge>
            <p className="mt-2 text-muted-foreground">
              {TOPICS.filter((t) => t.level === 'medium').length} topics — solid fundamentals and common interview areas
            </p>
          </div>
          <div>
            <Badge className={LEVEL_COLORS.light}>Light</Badge>
            <p className="mt-2 text-muted-foreground">
              {TOPICS.filter((t) => t.level === 'light').length} topics — key concepts and essential knowledge
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
