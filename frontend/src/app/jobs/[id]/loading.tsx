import { Skeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div className="space-y-2 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900" aria-busy="true" aria-label="Loading">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center gap-4 py-2">
          <Skeleton className="h-4 w-6" />
          <Skeleton className="size-6 rounded-full" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-2 w-24" />
          <Skeleton className="h-5 flex-1" />
        </div>
      ))}
    </div>
  );
}
