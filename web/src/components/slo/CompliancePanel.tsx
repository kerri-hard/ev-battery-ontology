'use client';

import { useEffect, useState } from 'react';
import { apiUrl } from '@/lib/api';
import GlassCard from '@/components/common/GlassCard';
import { EmptyState, LoadingState } from '@/components/common/StateMessages';

interface Regulation {
  id: string;
  name: string;
  description: string;
  category: string;
  country: string;
  effective_date: string;
}

interface ComplianceItem {
  id: string;
  name: string;
  regulation_id: string;
  kind: string;
}

interface AuditEvent {
  id: string;
  event_type: string;
  target_id: string;
  personnel_id: string;
  timestamp: string;
  details: string;
}

/** Compliance / Audit 거버넌스 패널 — SLO 페이지.
 *
 *  ISA-95 + UN R150 / IATF 16949 / EU Battery 표준 추적.
 *  외부 감사관이 한 번에 "어떤 규제 / 어떤 컴플라이언스 항목 / 누가 언제" 조회.
 */
export default function CompliancePanel() {
  const [regulations, setRegulations] = useState<Regulation[] | null>(null);
  const [items, setItems] = useState<ComplianceItem[]>([]);
  const [audits, setAudits] = useState<AuditEvent[]>([]);

  useEffect(() => {
    let mounted = true;
    fetch(apiUrl('/api/governance/compliance'))
      .then((r) => r.json())
      .then((d) => {
        if (mounted) {
          setRegulations(d.regulations ?? []);
          setItems(d.items ?? []);
        }
      })
      .catch(() => {
        if (mounted) setRegulations([]);
      });
    fetch(apiUrl('/api/governance/audit'))
      .then((r) => r.json())
      .then((d) => {
        if (mounted && Array.isArray(d.items)) setAudits(d.items);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  if (regulations === null) {
    return (
      <GlassCard className="p-3">
        <LoadingState label="거버넌스 로딩..." />
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-3">
      <div className="ds-label mb-2 flex items-center gap-2">
        <span>📜 Compliance / Audit (거버넌스)</span>
        <span className="pill-info ds-caption font-bold px-1.5 py-0.5 rounded">
          {regulations.length} 규제 · {audits.length} 감사
        </span>
      </div>

      {/* Regulations + ComplianceItems */}
      <div className="space-y-1.5 mb-2">
        {regulations.length === 0 ? (
          <EmptyState
            icon="📜"
            title="규제 없음"
            hint="engine 시작 시 UN R150 / IATF 16949 / EU Battery 자동 시드"
          />
        ) : (
          regulations.map((reg) => {
            const subItems = items.filter((c) => c.regulation_id === reg.id);
            return (
              <div
                key={reg.id}
                className="px-2 py-1.5 rounded bg-white/5 border-l-2 border-emerald-400/40"
              >
                <div className="flex items-center justify-between">
                  <div className="ds-body font-bold text-emerald-200/90">{reg.name}</div>
                  <div className="ds-caption text-white/40 font-mono">{reg.id}</div>
                </div>
                <div className="ds-caption text-white/60 mt-0.5">{reg.description}</div>
                {subItems.length > 0 && (
                  <div className="ds-caption text-white/50 mt-0.5 font-mono">
                    {subItems.map((s) => s.id).join(' · ')} ({subItems.length}개)
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* AuditTrail (최근 감사) */}
      {audits.length > 0 && (
        <div>
          <div className="ds-label mb-1 mt-2 text-amber-300/70">⏱ 최근 감사 이벤트</div>
          <div className="space-y-0.5 max-h-[200px] overflow-y-auto">
            {audits.slice(0, 10).map((a) => (
              <div key={a.id} className="ds-caption text-white/70 font-mono">
                <span
                  className={
                    a.event_type === 'hitl_approved'
                      ? 'text-emerald-300'
                      : a.event_type === 'hitl_denied'
                      ? 'text-rose-300'
                      : 'text-amber-300'
                  }
                >
                  {a.event_type}
                </span>
                <span className="text-white/30 mx-1">·</span>
                <span>{a.target_id || '?'}</span>
                <span className="text-white/30 mx-1">·</span>
                <span className="text-white/50">{a.personnel_id || 'anon'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </GlassCard>
  );
}
