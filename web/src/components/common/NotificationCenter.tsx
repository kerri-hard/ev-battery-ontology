'use client';

import { useEffect, useRef, useState } from 'react';
import { useEngine } from '@/context/EngineContext';

interface Toast {
  id: string;
  level: 'info' | 'warning' | 'danger';
  title: string;
  message: string;
  timestamp: number;
  navigate?: { view: 'overview' | 'healing' | 'slo' | 'learning' | 'console'; incidentId?: string | null };
}

const TOAST_DURATION_MS = 8000;

/** 우상단 toast 알림 시스템 — incident/HITL/SLO 위반 이벤트 자동 푸시 */
export default function NotificationCenter() {
  const { state, navigateTo } = useEngine();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const lastIncidentIdRef = useRef<string | null>(null);
  const lastHitlSeenRef = useRef<Set<string>>(new Set());
  const lastViolationsRef = useRef<Set<string>>(new Set());

  // 1. 새 incident 감지 (HIGH/CRITICAL만 toast)
  useEffect(() => {
    const incidents = state.healing.recentIncidents;
    if (incidents.length === 0) return;
    const newest = incidents[incidents.length - 1];
    if (!newest.id || newest.id === lastIncidentIdRef.current) return;
    lastIncidentIdRef.current = newest.id;

    const sev = newest.severity ?? '';
    if (sev !== 'HIGH' && sev !== 'CRITICAL') return;

    pushToast({
      id: `inc-${newest.id}`,
      level: sev === 'CRITICAL' ? 'danger' : 'warning',
      title: `${sev} incident 발생`,
      message: `${newest.id} · ${newest.step_id} · ${newest.top_cause}`,
      timestamp: Date.now(),
      navigate: { view: 'healing', incidentId: newest.id },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.healing.recentIncidents]);

  // 2. 새 HITL 대기 감지
  useEffect(() => {
    const pending = state.healing.hitlPending ?? [];
    const seen = lastHitlSeenRef.current;
    for (const h of pending) {
      const hid = String(h.id ?? '');
      const stepId = String(h.step_id ?? '');
      if (!hid || seen.has(hid)) continue;
      seen.add(hid);
      pushToast({
        id: `hitl-${hid}`,
        level: 'warning',
        title: '⏸ HITL 승인 대기',
        message: `${hid} · ${stepId} 운영자 승인 필요`,
        timestamp: Date.now(),
        navigate: { view: 'healing' },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.healing.hitlPending]);

  // 3. SLO 위반 감지 (새로 violation 추가됨)
  useEffect(() => {
    const violations = state.slo?.violations ?? [];
    const seen = lastViolationsRef.current;
    const currentKeys = new Set(violations.map((v) => v.sli));
    for (const v of violations) {
      if (seen.has(v.sli)) continue;
      seen.add(v.sli);
      pushToast({
        id: `slo-${v.sli}-${Date.now()}`,
        level: 'danger',
        title: '🔴 SLO 위반',
        message: `${v.name} ${(v.current * 100).toFixed(1)}% (목표 ${(v.target * 100).toFixed(1)}%)`,
        timestamp: Date.now(),
        navigate: { view: 'slo' },
      });
    }
    // 위반이 해소된 경우 seen에서 제거 (다음에 또 발생 시 알림)
    for (const k of Array.from(seen)) {
      if (!currentKeys.has(k)) seen.delete(k);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.slo?.violations]);

  function pushToast(t: Toast) {
    setToasts((prev) => {
      // 중복 id 방지
      if (prev.find((x) => x.id === t.id)) return prev;
      return [...prev, t].slice(-5); // 최대 5개
    });
    // 자동 dismiss
    setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== t.id));
    }, TOAST_DURATION_MS);
  }

  function dismiss(id: string) {
    setToasts((prev) => prev.filter((x) => x.id !== id));
  }

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-16 right-4 z-[100] flex flex-col gap-2 max-w-[360px] pointer-events-none">
      {toasts.map((t) => (
        <ToastCard
          key={t.id}
          toast={t}
          onDismiss={() => dismiss(t.id)}
          onClick={() => {
            if (t.navigate) {
              navigateTo(t.navigate);
              dismiss(t.id);
            }
          }}
        />
      ))}
    </div>
  );
}

function ToastCard({
  toast,
  onDismiss,
  onClick,
}: {
  toast: Toast;
  onDismiss: () => void;
  onClick: () => void;
}) {
  const cls =
    toast.level === 'danger'
      ? 'pill-danger'
      : toast.level === 'warning'
        ? 'pill-warning'
        : 'pill-info';
  return (
    <div
      className={`${cls} rounded-lg p-3 shadow-2xl pointer-events-auto cursor-pointer hover:opacity-90 transition animate-slide-in border`}
      onClick={onClick}
      style={{ backdropFilter: 'blur(20px)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="ds-body font-bold">{toast.title}</div>
          <div className="ds-caption mt-0.5">{toast.message}</div>
          {toast.navigate && (
            <div className="text-[8px] mt-1 opacity-70">
              클릭 → {viewLabel(toast.navigate.view)}로 이동
            </div>
          )}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          className="text-[10px] opacity-60 hover:opacity-100 px-1"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

function viewLabel(v: string): string {
  switch (v) {
    case 'overview':
      return 'Overview';
    case 'healing':
      return 'Healing';
    case 'slo':
      return 'SLO';
    case 'learning':
      return 'Learning';
    case 'console':
      return 'Console';
    default:
      return v;
  }
}
