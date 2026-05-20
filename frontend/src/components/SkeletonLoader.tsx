interface SkeletonLoaderProps {
  variant: 'card' | 'text' | 'circle' | 'clause-card';
  count?: number;
  className?: string;
}

function ClauseCardSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3 shadow-card">
      <div className="flex items-center justify-between">
        <div className="h-6 w-16 bg-gray-200 rounded-full animate-pulse" />
        <div className="h-5 w-10 bg-gray-200 rounded animate-pulse" />
      </div>
      <div className="bg-gray-50 rounded-lg p-3 space-y-2">
        <div className="h-4 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 bg-gray-200 rounded animate-pulse w-4/5" />
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4" />
        <div className="h-4 bg-gray-200 rounded animate-pulse w-1/2" />
      </div>
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-card animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
      <div className="h-4 bg-gray-200 rounded w-1/2" />
    </div>
  );
}

function TextSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      <div className="h-4 bg-gray-200 rounded" />
      <div className="h-4 bg-gray-200 rounded w-4/5" />
      <div className="h-4 bg-gray-200 rounded w-3/5" />
    </div>
  );
}

function CircleSkeleton() {
  return <div className="w-16 h-16 bg-gray-200 rounded-full animate-pulse" />;
}

export default function SkeletonLoader({ variant, count = 1, className = '' }: SkeletonLoaderProps) {
  const items = Array.from({ length: count });

  return (
    <div className={`space-y-4 ${className}`} aria-label="로딩 중..." aria-busy="true">
      {items.map((_, i) => {
        switch (variant) {
          case 'clause-card':
            return <ClauseCardSkeleton key={i} />;
          case 'card':
            return <CardSkeleton key={i} />;
          case 'text':
            return <TextSkeleton key={i} />;
          case 'circle':
            return <CircleSkeleton key={i} />;
          default:
            return <CardSkeleton key={i} />;
        }
      })}
    </div>
  );
}
