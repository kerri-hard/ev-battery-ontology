'use client';

import { useEffect, useMemo, useState } from 'react';
import { useEngine } from '@/context/EngineContext';

export default function ControlPanel() {
  const { state, sendCommand } = useEngine();
  const disabled = state.connectionStatus !== 'connected';
  const [minConfidence, setMinConfidence] = useState(0.62);
  const [highRiskThreshold, setHighRiskThreshold] = useState(0.6);
  const [mediumNeedsHistory, setMediumNeedsHistory] = useState(true);
  const [operatorName, setOperatorName] = useState('dashboard');
  const [operatorRole, setOperatorRole] = useState<'operator' | 'supervisor'>('operator');
  const [supervisorToken, setSupervisorToken] = useState('');

  useEffect(() => {
    const p = state.healing.hitlPolicy;
    if (!p) return;
    setMinConfidence(p.min_confidence);
    setHighRiskThreshold(p.high_risk_threshold);
    setMediumNeedsHistory(Boolean(p.medium_requires_history));
  }, [state.healing.hitlPolicy]);

  const policyDiff = useMemo(() => {
    const cur = state.healing.hitlPolicy;
    if (!cur) return [];
    const diff: Array<{ key: string; from: string; to: string }> = [];
    if (Number(cur.min_confidence).toFixed(2) !== minConfidence.toFixed(2)) {
      diff.push({ key: 'min_confidence', from: Number(cur.min_confidence).toFixed(2), to: minConfidence.toFixed(2) });
    }
    if (Number(cur.high_risk_threshold).toFixed(2) !== highRiskThreshold.toFixed(2)) {
      diff.push({ key: 'high_risk_threshold', from: Number(cur.high_risk_threshold).toFixed(2), to: highRiskThreshold.toFixed(2) });
    }
    if (Boolean(cur.medium_requires_history) !== mediumNeedsHistory) {
      diff.push({
        key: 'medium_requires_history',
        from: String(Boolean(cur.medium_requires_history)),
        to: String(mediumNeedsHistory),
      });
    }
    return diff;
  }, [state.healing.hitlPolicy, minConfidence, highRiskThreshold, mediumNeedsHistory]);

  const handleStart = () => {
    sendCommand({ cmd: 'init' });
    setTimeout(() => sendCommand({ cmd: 'run' }), 500);
  };

  return (
    <div className="space-y-3">
      <h3 className="text-xs text-text-dim font-medium">제어판</h3>

      {/* v3: 온톨로지 개선 */}
      <div className="text-[10px] text-text-dim uppercase tracking-wider">온톨로지 개선</div>
      <div className="grid grid-cols-2 gap-1.5">
        <button onClick={handleStart} disabled={disabled || state.running}
          className="text-xs py-1.5 px-2 rounded-lg bg-neon-green/20 border border-neon-green/30 text-neon-green hover:bg-neon-green/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
          {state.running ? '실행 중...' : '▶ 온톨로지'}
        </button>
        <button onClick={() => sendCommand({ cmd: 'step' })} disabled={disabled}
          className="text-xs py-1.5 px-2 rounded-lg bg-cyan/20 border border-cyan/30 text-cyan hover:bg-cyan/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
          ▷ 1회
        </button>
      </div>

      {/* v4: 자율 복구 */}
      <div className="text-[10px] text-text-dim uppercase tracking-wider mt-2">자율 복구</div>
      <div className="grid grid-cols-2 gap-1.5">
        <button onClick={() => { sendCommand({ cmd: 'init' }); setTimeout(() => sendCommand({ cmd: 'heal' }), 500); }}
          disabled={disabled || state.healing.running}
          className="text-xs py-1.5 px-2 rounded-lg bg-neon-purple/20 border border-neon-purple/30 text-neon-purple hover:bg-neon-purple/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
          {state.healing.running ? '복구 중...' : '⚡ 자율복구'}
        </button>
        <button onClick={() => sendCommand({ cmd: 'heal_step' })} disabled={disabled}
          className="text-xs py-1.5 px-2 rounded-lg bg-neon-orange/20 border border-neon-orange/30 text-neon-orange hover:bg-neon-orange/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
          ⚡ 1회
        </button>
      </div>

      {/* 전체 사이클 */}
      <button onClick={() => { sendCommand({ cmd: 'init' }); setTimeout(() => sendCommand({ cmd: 'full_cycle' }), 500); }}
        disabled={disabled || state.running || state.healing.running}
        className="w-full text-xs py-2 px-2 rounded-lg bg-gradient-to-r from-cyan/20 to-neon-purple/20 border border-cyan/20 text-white hover:from-cyan/30 hover:to-neon-purple/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
        🏭 전체 사이클 (온톨로지 + 자율복구)
      </button>

      {/* 제어 */}
      <div className="grid grid-cols-2 gap-1.5">
        <button onClick={() => sendCommand({ cmd: state.paused ? 'resume' : 'pause' })} disabled={disabled}
          className="text-xs py-1.5 px-2 rounded-lg bg-neon-yellow/20 border border-neon-yellow/30 text-neon-yellow hover:bg-neon-yellow/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
          {state.paused ? '▶ 재개' : '⏸ 일시정지'}
        </button>
        <button onClick={() => sendCommand({ cmd: 'reset' })} disabled={disabled}
          className="text-xs py-1.5 px-2 rounded-lg bg-neon-red/20 border border-neon-red/30 text-neon-red hover:bg-neon-red/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
          ⟲ 리셋
        </button>
      </div>

      {/* Speed Slider */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-dim">속도</span>
          <span className="text-xs font-mono text-text-primary">{state.speed.toFixed(1)}x</span>
        </div>
        <input
          type="range"
          min={0.1}
          max={3.0}
          step={0.1}
          value={state.speed}
          onChange={(e) => sendCommand({ cmd: 'speed', speed: parseFloat(e.target.value) })}
          disabled={disabled}
          className="w-full h-1 bg-white/10 rounded-full appearance-none cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3
            [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-cyan [&::-webkit-slider-thumb]:shadow-[0_0_6px_rgba(0,210,255,0.5)]
            disabled:opacity-40"
        />
      </div>

      {/* HITL Policy */}
      <div className="space-y-1.5 border-t border-white/10 pt-2">
        <div className="text-[10px] text-text-dim uppercase tracking-wider">HITL 정책</div>
        <div className="grid grid-cols-2 gap-1.5">
          <input
            value={operatorName}
            onChange={(e) => setOperatorName(e.target.value || 'dashboard')}
            disabled={disabled}
            placeholder="operator"
            className="text-[10px] px-2 py-1 rounded bg-white/5 border border-white/15 text-white/85 disabled:opacity-40"
          />
          <select
            value={operatorRole}
            onChange={(e) => setOperatorRole(e.target.value as 'operator' | 'supervisor')}
            disabled={disabled}
            className="text-[10px] px-2 py-1 rounded bg-white/5 border border-white/15 text-white/85 disabled:opacity-40"
          >
            <option value="operator">Operator</option>
            <option value="supervisor">Supervisor</option>
          </select>
        </div>
        {operatorRole === 'supervisor' && (
          <input
            value={supervisorToken}
            onChange={(e) => setSupervisorToken(e.target.value)}
            disabled={disabled}
            type="password"
            placeholder="Supervisor token"
            className="w-full text-[10px] px-2 py-1 rounded bg-white/5 border border-white/15 text-white/85 disabled:opacity-40"
          />
        )}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-white/60">최소 신뢰도</span>
            <span className="text-[10px] font-mono text-white/80">{minConfidence.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.3}
            max={0.95}
            step={0.01}
            value={minConfidence}
            onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
            disabled={disabled}
            className="w-full h-1 bg-white/10 rounded-full appearance-none cursor-pointer disabled:opacity-40"
          />
        </div>
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-white/60">고위험 임계</span>
            <span className="text-[10px] font-mono text-white/80">{highRiskThreshold.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.3}
            max={0.95}
            step={0.01}
            value={highRiskThreshold}
            onChange={(e) => setHighRiskThreshold(parseFloat(e.target.value))}
            disabled={disabled}
            className="w-full h-1 bg-white/10 rounded-full appearance-none cursor-pointer disabled:opacity-40"
          />
        </div>
        <label className="flex items-center gap-2 text-[10px] text-white/70">
          <input
            type="checkbox"
            checked={mediumNeedsHistory}
            onChange={(e) => setMediumNeedsHistory(e.target.checked)}
            disabled={disabled}
          />
          Medium 이상은 이력 매칭 필요
        </label>
        {policyDiff.length > 0 && (
          <div className="rounded border border-cyan/20 bg-cyan-500/5 p-1.5">
            <div className="text-[10px] text-cyan-200 mb-1">변경 diff</div>
            <div className="space-y-0.5">
              {policyDiff.map((d) => (
                <div key={d.key} className="text-[9px] font-mono text-cyan-100/90">
                  {d.key}: {d.from} {'->'} {d.to}
                </div>
              ))}
            </div>
          </div>
        )}
        {operatorRole !== 'supervisor' && (
          <div className="text-[9px] text-amber-300/90">
            정책 변경은 Supervisor 권한에서만 적용됩니다.
          </div>
        )}
        <button
          onClick={() => sendCommand({
            cmd: 'hitl_policy_update',
            min_confidence: minConfidence,
            high_risk_threshold: highRiskThreshold,
            medium_requires_history: mediumNeedsHistory,
            operator: operatorName || 'dashboard',
            role: operatorRole,
            supervisor_token: supervisorToken,
          })}
          disabled={disabled || policyDiff.length === 0}
          className="w-full text-[10px] py-1.5 px-2 rounded-lg bg-amber-500/20 border border-amber-400/30 text-amber-200 hover:bg-amber-500/30 disabled:opacity-40"
        >
          HITL 정책 적용
        </button>
        {(state.healing.hitlAudit?.length || 0) > 0 && (
          <div className="rounded border border-white/10 bg-white/5 p-1.5">
            <div className="text-[10px] text-white/65 mb-1">최근 HITL 감사로그</div>
            <div className="space-y-0.5 max-h-[84px] overflow-y-auto pr-1">
              {[...(state.healing.hitlAudit || [])].slice(-4).reverse().map((a, idx) => (
                <div key={`cp-audit-${idx}`} className="text-[9px]">
                  <span className="font-mono text-cyan-300 mr-1">{String(a.action || '-')}</span>
                  <span className="text-white/75">{String(a.operator || '-')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
