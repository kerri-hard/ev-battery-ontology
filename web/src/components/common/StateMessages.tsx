'use client';

/** 표준화된 빈 상태 / 로딩 상태 / 에러 상태 컴포넌트 */

interface BaseProps {
  className?: string;
}

/** 빈 상태 — 데이터가 아예 없을 때 (예: sim 시작 전) */
export function EmptyState({
  icon = '📭',
  title,
  hint,
  className = '',
}: BaseProps & { icon?: string; title: string; hint?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center py-6 px-3 text-center ${className}`}>
      <div className="text-2xl mb-2 opacity-50">{icon}</div>
      <div className="ds-body font-bold mb-0.5">{title}</div>
      {hint && <div className="ds-caption max-w-[280px]">{hint}</div>}
    </div>
  );
}

/** 로딩 상태 — 데이터 fetching 중 */
export function LoadingState({
  label = '데이터 로딩 중...',
  className = '',
}: BaseProps & { label?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center py-4 ${className}`}>
      {/* skeleton bars */}
      <div className="space-y-1.5 w-full max-w-[260px]">
        <div className="h-2 bg-white/10 rounded animate-pulse" />
        <div className="h-2 bg-white/10 rounded w-3/4 animate-pulse" />
        <div className="h-2 bg-white/10 rounded w-1/2 animate-pulse" />
      </div>
      <div className="ds-caption mt-2">{label}</div>
    </div>
  );
}

/** 에러 상태 — fetch 실패 등 */
export function ErrorState({
  title = '데이터를 불러오지 못했습니다',
  detail,
  onRetry,
  className = '',
}: BaseProps & { title?: string; detail?: string; onRetry?: () => void }) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-4 px-3 text-center pill-danger rounded ${className}`}
    >
      <div className="text-xl mb-1">⚠</div>
      <div className="ds-body font-bold">{title}</div>
      {detail && <div className="ds-caption mt-1">{detail}</div>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 text-[10px] px-2 py-1 rounded pill-info hover:opacity-90"
        >
          재시도
        </button>
      )}
    </div>
  );
}
