'use client';

import { useEngine } from '@/context/EngineContext';

export default function VoteResults() {
  const { state } = useEngine();
  const data = state.debate.votes;

  if (!data) {
    return <div className="text-text-dim text-xs py-2">투표 결과 대기 중...</div>;
  }

  const topVotes = data.top_votes.slice(0, 10);
  const maxScore = Math.max(...topVotes.map((v) => v.score), 1);

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className="flex items-center justify-between text-xs">
        <h4 className="font-bold text-text-primary">투표 결과</h4>
        <div className="flex gap-3 text-text-dim">
          <span>제안: <span className="font-mono text-text-primary">{data.total_proposals}</span></span>
          <span>비평: <span className="font-mono text-text-primary">{data.critiques}</span></span>
          <span className="text-neon-green">승인: {data.approved_count}</span>
          <span className="text-neon-red">거부: {data.rejected_count}</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-dim border-b border-white/5">
              <th className="text-left py-1 w-8">순위</th>
              <th className="text-left py-1">제안</th>
              <th className="text-left py-1 w-16">타입</th>
              <th className="text-left py-1 w-20">에이전트</th>
              <th className="text-left py-1 w-32">점수</th>
            </tr>
          </thead>
          <tbody>
            {topVotes.map((vote, idx) => {
              const passed = vote.score >= data.threshold;
              const barColor = passed ? 'bg-neon-green/60' : 'bg-neon-red/60';
              const barWidth = (vote.score / maxScore) * 100;
              const thresholdPos = (data.threshold / maxScore) * 100;

              return (
                <tr key={idx} className="border-b border-white/[0.03] hover:bg-white/[0.03]">
                  <td className="py-1 font-mono text-text-dim">{idx + 1}</td>
                  <td className="py-1 text-text-primary truncate max-w-[120px]">{vote.proposal}</td>
                  <td className="py-1 text-text-dim">{vote.action}</td>
                  <td className="py-1 text-text-dim">{vote.agent}</td>
                  <td className="py-1">
                    <div className="flex items-center gap-1.5">
                      <div className="relative flex-1 h-3 bg-white/5 rounded overflow-hidden">
                        <div
                          className={`h-full rounded ${barColor} transition-all`}
                          style={{ width: `${barWidth}%` }}
                        />
                        {/* Threshold line */}
                        <div
                          className="absolute top-0 h-full w-px bg-neon-yellow"
                          style={{ left: `${thresholdPos}%` }}
                        />
                      </div>
                      <span className="font-mono text-text-primary w-8 text-right">
                        {vote.score.toFixed(1)}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
