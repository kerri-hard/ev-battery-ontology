'use client';

import React, { useMemo } from 'react';
import { useEngine } from '@/context/EngineContext';
import { useState } from 'react';
import type { HealingIncident } from '@/types';
import { apiUrl } from '@/lib/api';

/* ── Healing keywords to filter from event log ── */
const HEALING_KEYWORDS = ['감지', '진단', '복구', '검증', '센서', '이상', '장애', 'heal', '자율', '정상'];

function severityColor(severity: string): string {
  switch (severity?.toUpperCase()) {
    case 'CRITICAL': return '#ef4444';
    case 'WARNING': return '#f59e0b';
    case 'INFO': return '#00d2ff';
    default: return '#6b7280';
  }
}

function severityBg(severity: string): string {
  switch (severity?.toUpperCase()) {
    case 'CRITICAL': return 'rgba(239, 68, 68, 0.1)';
    case 'WARNING': return 'rgba(245, 158, 11, 0.1)';
    default: return 'rgba(0, 210, 255, 0.05)';
  }
}

function requiresSupervisorApproval(reason: string): boolean {
  return reason.includes('high_risk') || reason.includes('low_confidence');
}

function csvEscape(value: unknown): string {
  const s = String(value ?? '');
  if (s.includes('"') || s.includes(',') || s.includes('\n')) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function LiveIssuePanel({ className = '' }: { className?: string }) {
  const { state, sendCommand } = useEngine();
  const { healing, eventLog } = state;
  const [selectedIncident, setSelectedIncident] = useState<HealingIncident | null>(null);
  const [operatorName, setOperatorName] = useState('dashboard');
  const [operatorRole, setOperatorRole] = useState<'operator' | 'supervisor'>('operator');
  const [supervisorToken, setSupervisorToken] = useState('');
  const [auditActionFilter, setAuditActionFilter] = useState<'all' | 'approved' | 'rejected' | 'policy_updated' | 'queued' | 'approve_denied' | 'policy_update_denied'>('all');
  const [auditRoleFilter, setAuditRoleFilter] = useState<'all' | 'operator' | 'supervisor'>('all');
  const [exportingCsv, setExportingCsv] = useState(false);

  /* Filter healing-related events from the event log */
  const healingEvents = useMemo(() => {
    return eventLog
      .filter(entry => HEALING_KEYWORDS.some(kw => entry.message.includes(kw)))
      .slice(-30)
      .reverse();
  }, [eventLog]);

  /* Determine active alarms from recent incidents */
  const activeAlarms = useMemo(() => {
    return healing.recentIncidents.filter(inc => !inc.auto_recovered).slice(-5);
  }, [healing.recentIncidents]);

  const recentIncidents = useMemo(() => {
    return [...healing.recentIncidents].slice(-12).reverse();
  }, [healing.recentIncidents]);

  const relatedEvents = useMemo(() => {
    if (!selectedIncident?.step_id) return [];
    return [...eventLog]
      .reverse()
      .filter((entry) =>
        entry.message.includes(selectedIncident.step_id) &&
        HEALING_KEYWORDS.some((kw) => entry.message.includes(kw)),
      )
      .slice(0, 10);
  }, [eventLog, selectedIncident?.step_id]);

  const recoveryRate = healing.incidents > 0
    ? ((healing.autoRecovered / healing.incidents) * 100).toFixed(0)
    : '0';

  const pendingItems = (healing.hitlPending || [])
    .filter((x) => (x.status as string | undefined) === 'pending')
    .slice(-3)
    .reverse();
  const resolvedItems = (healing.hitlPending || [])
    .filter((x) => (x.status as string | undefined) && (x.status as string) !== 'pending')
    .slice(-5)
    .reverse();
  const auditItems = useMemo(() => {
    const src = [...(healing.hitlAudit || [])].reverse();
    return src
      .filter((a) => (auditActionFilter === 'all' ? true : String(a.action || '') === auditActionFilter))
      .filter((a) => (auditRoleFilter === 'all' ? true : String(a.role || 'operator') === auditRoleFilter))
      .slice(0, 10);
  }, [healing.hitlAudit, auditActionFilter, auditRoleFilter]);

  const exportAuditCsv = async () => {
    setExportingCsv(true);
    try {
      let items = [...(healing.hitlAudit || [])];
      try {
        const resp = await fetch(apiUrl('/api/hitl/audit?limit=500'));
        if (resp.ok) {
          const body = await resp.json();
          if (Array.isArray(body?.items)) {
            items = body.items as Array<Record<string, unknown>>;
          }
        }
      } catch {
        // fallback to in-memory state
      }
      const filtered = items
        .filter((a) => (auditActionFilter === 'all' ? true : String(a.action || '') === auditActionFilter))
        .filter((a) => (auditRoleFilter === 'all' ? true : String(a.role || 'operator') === auditRoleFilter));
      const header = ['ts', 'action', 'operator', 'role', 'detail_json'];
      const lines = [header.join(',')];
      for (const row of filtered) {
        lines.push(
          [
            csvEscape(row.ts),
            csvEscape(row.action),
            csvEscape(row.operator),
            csvEscape(row.role || 'operator'),
            csvEscape(JSON.stringify(row.detail || {})),
          ].join(','),
        );
      }
      const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      a.href = url;
      a.download = `hitl_audit_${stamp}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExportingCsv(false);
    }
  };

  return (
    <div className={`flex flex-col h-full relative ${className}`}>
      {/* Active Alarms Section */}
      <div className="mb-3">
        {(healing.hitlPending?.length || 0) > 0 && (
          <div className="mb-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-2.5 py-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-amber-300">HITL 승인 대기</span>
              <span className="text-[10px] font-mono text-amber-200">{healing.hitlPending?.length}건</span>
            </div>
            {healing.hitlPolicy && (
              <div className="text-[9px] text-amber-100/80 mt-1">
                정책: conf≥{Number(healing.hitlPolicy.min_confidence).toFixed(2)} / risk≥{Number(healing.hitlPolicy.high_risk_threshold).toFixed(2)}
              </div>
            )}
            <div className="mt-1.5 space-y-1">
              <div className="grid grid-cols-2 gap-1">
                <input
                  value={operatorName}
                  onChange={(e) => setOperatorName(e.target.value || 'dashboard')}
                  className="text-[10px] px-1.5 py-1 rounded bg-black/20 border border-amber-300/20 text-amber-50"
                  placeholder="operator"
                />
                <select
                  value={operatorRole}
                  onChange={(e) => setOperatorRole(e.target.value as 'operator' | 'supervisor')}
                  className="text-[10px] px-1.5 py-1 rounded bg-black/20 border border-amber-300/20 text-amber-50"
                >
                  <option value="operator">Operator</option>
                  <option value="supervisor">Supervisor</option>
                </select>
              </div>
              {operatorRole === 'supervisor' && (
                <input
                  value={supervisorToken}
                  onChange={(e) => setSupervisorToken(e.target.value)}
                  type="password"
                  className="w-full text-[10px] px-1.5 py-1 rounded bg-black/20 border border-amber-300/20 text-amber-50"
                  placeholder="Supervisor token"
                />
              )}
              {pendingItems.map((p) => {
                const hid = String(p.id || '-');
                const reason = String(p.reason || 'policy_gate');
                const supervisorRequired = requiresSupervisorApproval(reason);
                const approveDisabled = supervisorRequired && operatorRole !== 'supervisor';
                return (
                  <div key={hid} className="rounded border border-amber-300/20 bg-black/20 px-2 py-1.5">
                    <div className="text-[10px] text-amber-100 font-mono">{hid} / {String(p.step_id || 'unknown')}</div>
                    <div className="text-[10px] text-amber-200/80 truncate">{reason}</div>
                    <div className="mt-1 flex gap-1.5">
                      <button
                        type="button"
                        disabled={approveDisabled}
                        title={approveDisabled ? 'Supervisor 권한이 필요합니다.' : '승인'}
                        onClick={() => sendCommand({
                          cmd: 'hitl_approve',
                          id: hid,
                          operator: operatorName || 'dashboard',
                          role: operatorRole,
                          supervisor_token: supervisorToken,
                        })}
                        className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-400/30 text-emerald-200 hover:bg-emerald-500/30 disabled:opacity-45 disabled:cursor-not-allowed"
                      >
                        승인
                      </button>
                      <button
                        type="button"
                        onClick={() => sendCommand({
                          cmd: 'hitl_reject',
                          id: hid,
                          operator: operatorName || 'dashboard',
                          role: operatorRole,
                          supervisor_token: supervisorToken,
                        })}
                        className="text-[10px] px-2 py-0.5 rounded bg-red-500/20 border border-red-400/30 text-red-200 hover:bg-red-500/30"
                      >
                        거절
                      </button>
                    </div>
                    {approveDisabled && (
                      <div className="mt-1 text-[9px] text-amber-200/85">고위험/저신뢰 승인에는 Supervisor가 필요합니다.</div>
                    )}
                  </div>
                );
              })}
            </div>
            {resolvedItems.length > 0 && (
              <div className="mt-1.5 pt-1.5 border-t border-amber-300/20">
                <div className="text-[9px] text-amber-100/80 mb-1">최근 처리 이력</div>
                <div className="space-y-1">
                  {resolvedItems.map((p) => (
                    <div key={`resolved-${String(p.id)}`} className="text-[9px] text-amber-50/80 bg-black/15 rounded px-1.5 py-1 border border-amber-300/10">
                      {String(p.id)} / {String(p.status)} / {String(p.operator || '-')} ({String(p.operator_role || 'operator')})
                    </div>
                  ))}
                </div>
              </div>
            )}
            {auditItems.length > 0 && (
              <div className="mt-1.5 pt-1.5 border-t border-amber-300/20">
                <div className="flex items-center gap-1 mb-1">
                  <div className="text-[9px] text-amber-100/80">운영 감사 로그</div>
                  <select
                    value={auditActionFilter}
                    onChange={(e) => setAuditActionFilter(e.target.value as 'all' | 'approved' | 'rejected' | 'policy_updated' | 'queued' | 'approve_denied' | 'policy_update_denied')}
                    className="text-[9px] px-1 py-0.5 rounded bg-black/20 border border-amber-300/20 text-amber-50"
                  >
                    <option value="all">all</option>
                    <option value="queued">queued</option>
                    <option value="approved">approved</option>
                    <option value="rejected">rejected</option>
                    <option value="policy_updated">policy</option>
                    <option value="approve_denied">approve_denied</option>
                    <option value="policy_update_denied">policy_denied</option>
                  </select>
                  <select
                    value={auditRoleFilter}
                    onChange={(e) => setAuditRoleFilter(e.target.value as 'all' | 'operator' | 'supervisor')}
                    className="text-[9px] px-1 py-0.5 rounded bg-black/20 border border-amber-300/20 text-amber-50"
                  >
                    <option value="all">role</option>
                    <option value="operator">operator</option>
                    <option value="supervisor">supervisor</option>
                  </select>
                  <button
                    type="button"
                    onClick={exportAuditCsv}
                    disabled={exportingCsv}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/20 border border-cyan-300/30 text-cyan-100 hover:bg-cyan-500/30 disabled:opacity-50"
                  >
                    {exportingCsv ? 'export...' : 'CSV'}
                  </button>
                </div>
                <div className="space-y-1 max-h-[80px] overflow-y-auto">
                  {auditItems.map((a, idx) => (
                    <div key={`audit-${idx}`} className="text-[9px] text-amber-50/80 bg-black/15 rounded px-1.5 py-1 border border-amber-300/10">
                      <span className="font-mono text-amber-200/80 mr-1">{String(a.action || '-')}</span>
                      <span>{String(a.operator || '-')}</span>
                      <span className="text-amber-100/60">{' '}({String(a.role || 'operator')})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-2 mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-[#ef4444] animate-pulse" />
          <h3 className="text-xs font-bold text-text-primary">활성 알람</h3>
          <span className="ml-auto text-[10px] font-mono text-text-dim">
            {activeAlarms.length > 0 ? `${activeAlarms.length}건` : '없음'}
          </span>
        </div>
        {activeAlarms.length > 0 ? (
          <div className="space-y-1.5 max-h-[120px] overflow-y-auto">
            {activeAlarms.map((alarm, i) => (
              <div
                key={`alarm-${i}`}
                className="rounded-lg px-2.5 py-2 animate-fade-in"
                style={{
                  background: severityBg('CRITICAL'),
                  border: `1px solid ${severityColor('CRITICAL')}33`,
                }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                    style={{
                      color: severityColor('CRITICAL'),
                      background: `${severityColor('CRITICAL')}22`,
                    }}
                  >
                    CRITICAL
                  </span>
                  <span className="text-[10px] font-mono text-text-dim">{alarm.step_id}</span>
                </div>
                <div className="text-[11px] text-text-primary">
                  {alarm.cause || alarm.top_cause || '원인 분석 중'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-[11px] text-text-dim text-center py-3 rounded-lg"
            style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.1)' }}>
            모든 공정 정상 운영 중
          </div>
        )}
      </div>

      {/* Recent incidents list */}
      <div className="mb-3">
        <div className="flex items-center gap-2 mb-2">
          <h3 className="text-xs font-bold text-text-primary">실시간 이슈 목록</h3>
          <span className="ml-auto text-[10px] font-mono text-text-dim">{recentIncidents.length}건</span>
        </div>
        <div className="space-y-1.5 max-h-[150px] overflow-y-auto pr-1">
          {recentIncidents.length === 0 ? (
            <div className="text-[11px] text-text-dim text-center py-3 rounded-lg"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
              기록된 이슈가 없습니다
            </div>
          ) : (
            recentIncidents.map((inc) => (
              <button
                key={inc.id || `${inc.step_id}-${inc.timestamp}`}
                type="button"
                onClick={() => setSelectedIncident(inc)}
                className="w-full text-left rounded-lg px-2.5 py-2 border border-white/10 hover:border-cyan/40 transition-colors"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-mono text-white/70">{inc.step_id}</span>
                  <span className={`text-[9px] font-bold ${inc.auto_recovered ? 'text-emerald-300' : 'text-red-300'}`}>
                    {inc.auto_recovered ? 'AUTO' : 'MANUAL'}
                  </span>
                </div>
                <div className="text-[11px] text-text-primary truncate">
                  {inc.anomaly_type || 'unknown'} / {inc.top_cause || inc.cause || 'unknown'}
                </div>
                <div className="flex items-center gap-1 mt-1">
                  {inc.history_matched && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-200">FailureChain</span>
                  )}
                  {inc.hitl_required && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-200">HITL</span>
                  )}
                  {!!inc.causal_chain && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-200">Causal</span>
                  )}
                </div>
                <div className="text-[10px] text-text-dim">
                  조치: {inc.action_type || inc.action || 'unknown'}
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Auto-Recovery Timeline */}
      <div className="flex-1 min-h-0 mb-3">
        <h3 className="text-xs font-bold text-text-primary mb-2">복구 타임라인</h3>
        <div className="space-y-1 max-h-[200px] overflow-y-auto pr-1">
          {healingEvents.length > 0 ? (
            healingEvents.map((entry, i) => {
              const isRecovery = entry.message.includes('복구');
              const isDetect = entry.message.includes('감지') || entry.message.includes('이상');
              const isDiagnose = entry.message.includes('진단');
              const isNormal = entry.message.includes('정상');

              let dotColor = '#6b7280';
              if (isRecovery) dotColor = '#10b981';
              else if (isDetect) dotColor = '#ef4444';
              else if (isDiagnose) dotColor = '#f59e0b';
              else if (isNormal) dotColor = '#00d2ff';

              return (
                <div key={`evt-${i}`} className="flex items-start gap-2 animate-fade-in">
                  {/* Timeline dot */}
                  <div className="flex flex-col items-center flex-shrink-0 mt-1">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ background: dotColor, boxShadow: `0 0 6px ${dotColor}66` }}
                    />
                    {i < healingEvents.length - 1 && (
                      <div className="w-px h-3 bg-white/10 mt-0.5" />
                    )}
                  </div>
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-mono text-text-dim">[{entry.ts}]</span>
                    </div>
                    <div className="text-[11px] text-text-primary leading-tight truncate">
                      {entry.message}
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="text-[11px] text-text-dim text-center py-6">
              복구 이력 없음
            </div>
          )}
        </div>
      </div>

      {/* Statistics */}
      <div className="border-t border-white/5 pt-2">
        <h3 className="text-xs font-bold text-text-primary mb-2">통계</h3>
        <div className="grid grid-cols-3 gap-2">
          <div className="text-center">
            <div className="text-lg font-bold font-mono text-[#ef4444]">
              {healing.incidents}
            </div>
            <div className="text-[9px] text-text-dim">장애 감지</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold font-mono text-[#10b981]">
              {recoveryRate}%
            </div>
            <div className="text-[9px] text-text-dim">복구율</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold font-mono text-[#00d2ff]">
              {healing.autoRecovered}
            </div>
            <div className="text-[9px] text-text-dim">자동 복구</div>
          </div>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <div className="text-center rounded-md border border-white/10 py-1.5">
            <div className="text-[12px] font-mono text-violet-300">
              {(((healing.recurrenceKpis?.matched_chain_rate || 0) * 100)).toFixed(0)}%
            </div>
            <div className="text-[9px] text-text-dim">체인 적중률</div>
          </div>
          <div className="text-center rounded-md border border-white/10 py-1.5">
            <div className="text-[12px] font-mono text-amber-300">
              {(((healing.recurrenceKpis?.repeat_incident_rate || 0) * 100)).toFixed(0)}%
            </div>
            <div className="text-[9px] text-text-dim">재발 비율</div>
          </div>
          <div className="text-center rounded-md border border-white/10 py-1.5">
            <div className="text-[12px] font-mono text-emerald-300">
              {(((healing.recurrenceKpis?.matched_auto_recovery_rate || 0) * 100)).toFixed(0)}%
            </div>
            <div className="text-[9px] text-text-dim">체인기반 자동복구</div>
          </div>
        </div>
        <div className="mt-2 rounded-md border border-white/10 px-2 py-1.5 text-[10px]">
          <div className="text-white/60 mb-0.5">재발 MTTR (sec)</div>
          <div className="font-mono text-cyan-200">
            matched {Number(healing.recurrenceKpis?.matched_avg_recovery_sec || 0).toFixed(3)}
            {' / '}
            unmatched {Number(healing.recurrenceKpis?.unmatched_avg_recovery_sec || 0).toFixed(3)}
          </div>
        </div>
        <div className="mt-2 rounded-md border border-white/10 px-2 py-1.5 text-[10px]">
          <div className="text-white/60 mb-0.5">Playbook 적용 품질</div>
          <div className="font-mono text-violet-200">
            graph {Number((Number(healing.recurrenceKpis?.graph_playbook_rate || 0) * 100)).toFixed(0)}%
            {' / '}
            fallback {Number((Number(healing.recurrenceKpis?.hardcoded_fallback_rate || 0) * 100)).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* Issue detail modal */}
      {selectedIncident && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/55 p-3">
          <div className="w-full max-w-[460px] rounded-xl border border-cyan/30 p-3"
            style={{ background: 'rgba(10, 12, 26, 0.98)', backdropFilter: 'blur(12px)' }}>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-bold text-white/90">이슈 상세 분석</h4>
              <button
                type="button"
                onClick={() => setSelectedIncident(null)}
                className="text-[11px] text-white/60 hover:text-white"
              >
                닫기
              </button>
            </div>

            <div className="space-y-1.5 text-[11px]">
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">Incident ID</span>
                <span className="font-mono text-white/85">{selectedIncident.id || '-'}</span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">공정 Step</span>
                <span className="font-mono text-white/85">{selectedIncident.step_id}</span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">이슈 유형</span>
                <span className="text-white/85">{selectedIncident.anomaly_type || '-'}</span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">원인 추정</span>
                <span className="text-white/85">{selectedIncident.top_cause || selectedIncident.cause || '-'}</span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">신뢰도</span>
                <span className="text-white/85">{selectedIncident.confidence !== undefined ? `${(selectedIncident.confidence * 100).toFixed(1)}%` : '-'}</span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">복구 액션</span>
                <span className="text-white/85">{selectedIncident.action_type || selectedIncident.action || '-'}</span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">Playbook</span>
                <span className="text-white/85 font-mono">
                  {selectedIncident.playbook_id || '-'}
                  {selectedIncident.playbook_source ? ` / ${selectedIncident.playbook_source}` : ''}
                </span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">자동 복구</span>
                <span className={selectedIncident.auto_recovered ? 'text-emerald-300' : 'text-red-300'}>
                  {selectedIncident.auto_recovered ? '성공' : '실패/수동 필요'}
                </span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">전/후 수율</span>
                <span className="font-mono text-white/85">
                  {selectedIncident.pre_yield !== undefined ? selectedIncident.pre_yield.toFixed(4) : '-'}
                  {' -> '}
                  {selectedIncident.post_yield !== undefined ? selectedIncident.post_yield.toFixed(4) : '-'}
                </span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">인과 체인</span>
                <span className="text-white/85 break-words">{selectedIncident.causal_chain || '-'}</span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">근거 품질</span>
                <span className="text-white/80">
                  {selectedIncident.analysis_method || 'causal_reasoning'}
                  {' / 후보 '}
                  {selectedIncident.candidates_count ?? 0}
                  {' / 체인 '}
                  {selectedIncident.causal_chains_found ?? 0}
                  {selectedIncident.history_matched ? ' / 과거체인매칭' : ''}
                </span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">패턴 매칭</span>
                <span className="text-white/80">
                  {selectedIncident.matched_pattern_type || '-'}
                  {selectedIncident.matched_pattern_id ? ` (${selectedIncident.matched_pattern_id})` : ''}
                </span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">근거 ID</span>
                <span className="text-white/80 font-mono">
                  {selectedIncident.matched_chain_id || '-'}
                </span>
              </div>
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">근거 참조</span>
                <span className="text-white/80 break-words font-mono">
                  {(selectedIncident.evidence_refs || []).join(', ') || '-'}
                </span>
              </div>
              {selectedIncident.rca_score_breakdown && (
                <div className="grid grid-cols-[90px_1fr] gap-1">
                  <span className="text-white/40">RCA 점수</span>
                  <span className="text-white/80 font-mono">
                    base {Number(selectedIncident.rca_score_breakdown.base || 0).toFixed(2)}
                    {' / '}causal {Number(selectedIncident.rca_score_breakdown.causal_strength || 0).toFixed(2)}
                    {' / '}history {Number(selectedIncident.rca_score_breakdown.history_match || 0).toFixed(2)}
                    {' / '}pattern {Number(selectedIncident.rca_score_breakdown.pattern_similarity || 0).toFixed(2)}
                  </span>
                </div>
              )}
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">리스크/HITL</span>
                <span className="text-white/80">
                  {selectedIncident.risk_level || '-'}
                  {selectedIncident.hitl_required ? ` / 필요 (${selectedIncident.hitl_id || '-'})` : ' / 불필요'}
                </span>
              </div>
              {selectedIncident.escalation_reason && (
                <div className="grid grid-cols-[90px_1fr] gap-1">
                  <span className="text-white/40">에스컬레이션</span>
                  <span className="text-amber-200 break-words">{selectedIncident.escalation_reason}</span>
                </div>
              )}
              <div className="grid grid-cols-[90px_1fr] gap-1">
                <span className="text-white/40">발생 시각</span>
                <span className="text-white/75 font-mono">{selectedIncident.timestamp || '-'}</span>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-white/10">
              <div className="text-[11px] font-semibold text-white/85 mb-1.5">관련 이벤트 로그 (자동 필터)</div>
              <div className="max-h-[120px] overflow-y-auto space-y-1 pr-1">
                {relatedEvents.length === 0 ? (
                  <div className="text-[10px] text-white/45">해당 Step 관련 로그가 아직 없습니다.</div>
                ) : (
                  relatedEvents.map((entry, idx) => (
                    <div key={`related-${idx}`} className="text-[10px] rounded px-2 py-1 bg-white/5 border border-white/10">
                      <span className="font-mono text-white/45 mr-1">[{entry.ts}]</span>
                      <span className="text-white/80">{entry.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default React.memo(LiveIssuePanel);
