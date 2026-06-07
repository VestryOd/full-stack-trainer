'use client';

import Link from 'next/link';
import { TOPICS } from '@/constants/topics';
import { useLocale } from '@/context/LocaleContext';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

const SECTIONS = [
  { href: '/theory',    titleKey: 'nav.theory',    descKey: 'home.theoryDesc',    icon: '📖' },
  { href: '/questions', titleKey: 'nav.questions', descKey: 'home.questionsDesc', icon: '❓' },
  { href: '/quiz',      titleKey: 'nav.quiz',      descKey: 'home.quizDesc',      icon: '🧠' },
  { href: '/tasks',     titleKey: 'nav.tasks',     descKey: 'home.tasksDesc',     icon: '💻' },
] as const;

const LEVEL_COLORS = {
  deep:   'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  medium: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  light:  'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
};

export default function HomePage() {
  const { t2 } = useLocale();

  return (
    <div className="container py-10 space-y-12">
      <section className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">Full Stack Trainer</h1>
        <p className="text-muted-foreground text-lg max-w-xl mx-auto">
          {t2('home.subtitle')}
        </p>
        <div className="flex justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/theory">{t2('home.btnTheory')}</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/quiz">{t2('home.btnQuiz')}</Link>
          </Button>
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-6">{t2('home.sections')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {SECTIONS.map((s) => (
            <Link key={s.href} href={s.href}>
              <Card className="section-card h-full transition-colors hover:bg-accent cursor-pointer">
                <CardHeader>
                  <div className="icon text-3xl mb-2 mx-auto sm:mx-0 w-fit">{s.icon}</div>
                  <CardTitle className="text-center sm:text-left">{t2(s.titleKey)}</CardTitle>
                  <CardDescription className="text-center sm:text-left">{t2(s.descKey)}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold mb-6">{t2('home.topics')} ({TOPICS.length})</h2>
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
        <h2 className="text-xl font-semibold mb-3">{t2('home.coverageLevels')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <Badge className={LEVEL_COLORS.deep}>Deep</Badge>
            <p className="mt-2 text-muted-foreground">
              {t2('home.deepDesc')}
            </p>
          </div>
          <div>
            <Badge className={LEVEL_COLORS.medium}>Medium</Badge>
            <p className="mt-2 text-muted-foreground">
              {t2('home.mediumDesc')}
            </p>
          </div>
          <div>
            <Badge className={LEVEL_COLORS.light}>Light</Badge>
            <p className="mt-2 text-muted-foreground">
              {t2('home.lightDesc')}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
