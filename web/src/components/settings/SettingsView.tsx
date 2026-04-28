'use client';

import { useEffect, useState } from 'react';
import { apiUrl } from '@/lib/api';
import { useEngine } from '@/context/EngineContext';
import GlassCard from '@/components/common/GlassCard';
import { LoadingState } from '@/components/common/StateMessages';

interface HitlPolicy {
  min_confidence: number;
  high_risk_threshold: number;
  medium_requires_history: boolean;
}

/** Settings — HITL 정책 편집 + 키보드 단축키 안내. */
export default function SettingsView() {
  const { state, sendCommand } = useEngine();
  const [policy, setPolicy] = useState<HitlPolicy | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'ok' | 'err'; msg: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;
    fetch(apiUrl('/api/hitl/policy'))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && mounted) setPolicy(data);
      })
      .catch(() => {
        // ignore — fall back to engine state
        if (mounted) setPolicy(state.healing.hitlPolicy ?? null);
      });
    return () => {
      mounted = false;
    };
  }, [state.healing.hitlPolicy]);

  if (!policy) {
    return (
      <GlassCard>
        <LoadingState label="HITL 정책 로딩..." />
      </GlassCard>
    );
  }

  function update<K extends keyof HitlPolicy>(key: K, value: HitlPolicy[K]) {
    setPolicy((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function save() {
    if (!policy) return;
    setSaving(true);
    setFeedback(null);
    try {
      sendCommand({
        cmd: 'hitl_policy_update',
        min_confidence: policy.min_confidence,
        high_risk_threshold: policy.high_risk_threshold,
        medium_requires_history: policy.medium_requires_history,
        operator: 'settings-ui',
      });
      setFeedback({ type: 'ok', msg: '✓ HITL 정책 업데이트 (실시간 적용)' });
      setTimeout(() => setFeedback(null), 3000);
    } catch (e) {
      setFeedback({ type: 'err', msg: String(e) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 max-w-2xl">
      <GlassCard className="p-4">
        <div className="ds-label mb-2">⏸ HITL 정책 — 안전등급별 자동 승인 기준</div>
        <div className="space-y-3">
          <SliderRow
            label="min_confidence"
            desc="이 신뢰도 미만 액션은 HITL 강제 (낮을수록 자동화 ↑, 안전 ↓)"
            value={policy.min_confidence}
            min={0}
            max={1}
            step={0.01}
            onChange={(v) => update('min_confidence', v)}
            format={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <SliderRow
            label="high_risk_threshold"
            desc="이 risk 이상 액션은 HITL 강제 (낮을수록 보수적)"
            value={policy.high_risk_threshold}
            min={0}
            max={1}
            step={0.05}
            onChange={(v) => update('high_risk_threshold', v)}
            format={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <CheckboxRow
            label="medium_requires_history"
            desc="MEDIUM 위험 액션은 과거 매칭 history 있을 때만 자동"
            checked={policy.medium_requires_history}
            onChange={(v) => update('medium_requires_history', v)}
          />
        </div>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/10">
          <div className="ds-caption">
            현재 HITL 대기 {state.healing.hitlPending?.length ?? 0}건
          </div>
          <button
            onClick={save}
            disabled={saving}
            className="px-3 py-1.5 rounded pill-info hover:opacity-90 transition text-[11px] font-bold disabled:opacity-50"
            aria-label="HITL 정책 저장 및 적용"
          >
            {saving ? '저장 중...' : '✓ 적용'}
          </button>
        </div>
        {feedback && (
          <div
            className={`mt-2 px-2 py-1.5 rounded ds-caption ${
              feedback.type === 'ok' ? 'pill-success' : 'pill-danger'
            }`}
          >
            {feedback.msg}
          </div>
        )}
      </GlassCard>

      <GlassCard className="p-4">
        <div className="ds-label mb-2">⌨ 키보드 단축키</div>
        <div className="grid grid-cols-2 gap-y-1.5 gap-x-4">
          <Kbd k="g o" desc="🏠 Overview" />
          <Kbd k="g h" desc="🛡 Healing" />
          <Kbd k="g s" desc="📊 SLO" />
          <Kbd k="g l" desc="🧠 Learning" />
          <Kbd k="g c" desc="🖥 Console" />
          <Kbd k="Esc" desc="선택 해제" />
          <Kbd k="?" desc="도움말 토글" />
        </div>
      </GlassCard>

      <GlassCard className="p-4">
        <div className="ds-label mb-2">ℹ 시스템 정보</div>
        <div className="grid grid-cols-2 gap-y-1 ds-body">
          <span className="text-white/50">현재 healing iter</span>
          <span className="font-mono text-cyan-300">{state.healing.iteration}</span>
          <span className="text-white/50">총 incident</span>
          <span className="font-mono text-cyan-300">{state.healing.incidents}</span>
          <span className="text-white/50">자동 복구</span>
          <span className="font-mono text-emerald-300">{state.healing.autoRecovered}</span>
          <span className="text-white/50">SLO 위반</span>
          <span className="font-mono text-rose-300">{state.slo?.violations.length ?? 0}건</span>
        </div>
      </GlassCard>
    </div>
  );
}

function SliderRow({
  label,
  desc,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  desc: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-0.5">
        <span className="ds-body font-bold">{label}</span>
        <span className="ds-body font-mono text-cyan-300">{format(value)}</span>
      </div>
      <div className="ds-caption mb-1.5">{desc}</div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
        aria-label={label}
      />
    </div>
  );
}

function CheckboxRow({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1"
        aria-label={label}
      />
      <div>
        <div className="ds-body font-bold">{label}</div>
        <div className="ds-caption">{desc}</div>
      </div>
    </label>
  );
}

function Kbd({ k, desc }: { k: string; desc: string }) {
  return (
    <div className="flex items-center gap-2">
      <kbd className="text-[10px] font-mono px-2 py-0.5 rounded border border-white/20 bg-white/5 text-white/80 min-w-[40px] text-center">
        {k}
      </kbd>
      <span className="ds-body text-white/70">{desc}</span>
    </div>
  );
}
