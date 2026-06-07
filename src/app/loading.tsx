import { Skeleton } from '@/components/ui/skeleton';

export default function Loading() {
  return (
    <div className="container py-10 space-y-12">
      <section className="text-center space-y-4">
        <Skeleton className="h-10 w-72 mx-auto" />
        <Skeleton className="h-5 w-full max-w-xl mx-auto" />
        <Skeleton className="h-5 w-2/3 max-w-xl mx-auto" />
        <div className="flex justify-center gap-3">
          <Skeleton className="h-11 w-32" />
          <Skeleton className="h-11 w-32" />
        </div>
      </section>

      <section>
        <Skeleton className="h-7 w-32 mb-6" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-lg" />
          ))}
        </div>
      </section>
    </div>
  );
}
