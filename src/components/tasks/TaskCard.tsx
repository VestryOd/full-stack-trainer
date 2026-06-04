import Link from 'next/link';
import type { Task } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface TaskCardProps {
  task: Task;
  locale: 'en' | 'ru';
}

const DIFFICULTY_COLORS: Record<Task['difficulty'], string> = {
  easy:   'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  hard:   'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

export function TaskCard({ task, locale }: TaskCardProps) {
  return (
    <Link href={`/tasks/${task.topicId}/${task.id}`}>
      <Card className="transition-colors hover:bg-accent cursor-pointer h-full">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">{task.title[locale]}</CardTitle>
            <Badge variant="outline" className={DIFFICULTY_COLORS[task.difficulty]}>
              {task.difficulty}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground line-clamp-2">{task.description[locale]}</p>
          <div className="mt-3 flex flex-wrap gap-1">
            {task.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
