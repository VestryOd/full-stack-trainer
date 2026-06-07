import Link from 'next/link';
import { TOPICS } from '@/constants/topics';
import { getTopicArticleCount } from '@/lib/content';
import { cn } from '@/lib/utils';

const LEVEL_STYLES: Record<string, string> = {
  deep:   'bg-blue-500/10 text-blue-400 border-blue-500/20',
  medium: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  light:  'bg-muted text-muted-foreground border-border',
};

export default function TheoryPage() {
  const topicsWithCounts = TOPICS.map((t) => ({
    ...t,
    articleCount: getTopicArticleCount(t.id),
  }));

  const available = topicsWithCounts.filter((t) => t.articleCount > 0);
  const upcoming  = topicsWithCounts.filter((t) => t.articleCount === 0);

  return (
    <div className="container py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-mono font-semibold">Theory</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {available.length} topics available · {available.reduce((sum, t) => sum + t.articleCount, 0)} articles
        </p>
      </div>

      {/* Topics with content */}
      <section className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {available.map((topic) => (
            <Link
              key={topic.id}
              href={`/theory/${topic.id}`}
              className="group flex items-center justify-between p-4 bg-card border border-border rounded-md hover:border-muted-foreground/50 transition-colors"
            >
              <div>
                <p className="text-sm font-medium group-hover:text-foreground transition-colors">
                  {topic.label}
                </p>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">
                  {topic.articleCount} articles
                </p>
              </div>
              <span
                className={cn(
                  'text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border flex-shrink-0',
                  LEVEL_STYLES[topic.level],
                )}
              >
                {topic.level}
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Upcoming topics */}
      {upcoming.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-mono text-muted-foreground uppercase tracking-wide">
            Coming soon ({upcoming.length})
          </h2>
          <div className="flex flex-wrap gap-2">
            {upcoming.map((topic) => (
              <span
                key={topic.id}
                className="inline-flex items-center px-2.5 py-1 rounded border border-border text-xs text-muted-foreground font-mono opacity-50"
              >
                {topic.label}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
