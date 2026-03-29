'use client';

import { useEngine } from '@/context/EngineContext';

export default function ApplyResults() {
  const { state } = useEngine();
  const data = state.debate.applied;

  if (!data) {
    return <div className="text-text-dim text-xs py-2">적용 결과 대기 중...</div>;
  }

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-bold text-text-primary">적용 결과</h4>

      {/* Summary cards */}
      <div className="flex gap-2">
        <div className="flex-1 rounded-lg bg-neon-green/10 border border-neon-green/20 p-2 text-center">
          <div className="text-lg font-bold font-mono text-neon-green">{data.applied}</div>
          <div className="text-[10px] text-text-dim">적용 성공</div>
        </div>
        <div className="flex-1 rounded-lg bg-neon-red/10 border border-neon-red/20 p-2 text-center">
          <div className="text-lg font-bold font-mono text-neon-red">{data.failed}</div>
          <div className="text-[10px] text-text-dim">적용 실패</div>
        </div>
      </div>

      {/* Details list */}
      <div className="space-y-1 max-h-[200px] overflow-y-auto">
        {data.details.map((detail) => {
          const success = detail.status === 'applied' || detail.status === 'success';
          return (
            <div
              key={detail.id}
              className="flex items-center gap-2 text-xs py-1 px-1.5 rounded bg-white/[0.02]"
            >
              <span className={success ? 'text-neon-green' : 'text-neon-red'}>
                {success ? '\u2713' : '\u2717'}
              </span>
              <span className="text-text-dim w-16 truncate">{detail.action}</span>
              <span className="text-text-primary flex-1 truncate">{detail.skill}</span>
              <span className="text-text-dim truncate">{detail.agent}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
