import Link from 'next/link';
import { TOPICS } from '@/constants/topics';
import { getAllTasks } from '@/lib/tasks';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function TasksPage() {
  const allTasks = getAllTasks();

  const topicsWithTasks = TOPICS.filter((topic) =>
    allTasks.some((t) => t.topicId === topic.id),
  );

  return (
    <div className="container py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Tasks</h1>
        <p className="text-muted-foreground mt-1">
          Coding challenges — {allTasks.length} tasks across {topicsWithTasks.length} topics
        </p>
      </div>
      {topicsWithTasks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {topicsWithTasks.map((topic) => {
            const count = allTasks.filter((t) => t.topicId === topic.id).length;
            return (
              <Link key={topic.id} href={`/tasks/${topic.id}`}>
                <Card className="h-full transition-colors hover:bg-accent cursor-pointer">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">{topic.label}</CardTitle>
                      <Badge variant="secondary">{count}</Badge>
                    </div>
                    <CardDescription>{count} tasks</CardDescription>
                  </CardHeader>
                </Card>
              </Link>
            );
          })}
        </div>
      ) : (
        <p className="text-center text-muted-foreground py-12">
          No tasks yet. Add content via Prompt 2.
        </p>
      )}
    </div>
  );
}
