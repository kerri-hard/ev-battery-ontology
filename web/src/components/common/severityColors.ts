/** Severity / Status / Phase 색상 단일 매핑 — 3+ 컴포넌트의 중복 함수 통합.
 *  globals.css의 pill-* / ds-* 토큰을 반환하여 시각 일관성 보장.
 */

export type SeverityKey = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | string | undefined;

/** Severity 칩 클래스 (pill-danger/warning/info/success).
 *  사용 예: <span className={severityToPill('HIGH')}>...</span>
 */
export function severityToPill(sev: SeverityKey): string {
  switch (sev) {
    case 'CRITICAL':
      return 'pill-danger';
    case 'HIGH':
      return 'pill-danger';
    case 'MEDIUM':
      return 'pill-warning';
    case 'LOW':
      return 'pill-success';
    default:
      return 'bg-white/10 text-white/50';
  }
}

/** Severity → CSS 변수 색상 (SVG 차트나 inline style 용) */
export function severityToColor(sev: SeverityKey): string {
  switch (sev) {
    case 'CRITICAL':
    case 'HIGH':
      return 'var(--color-danger)';
    case 'MEDIUM':
      return 'var(--color-warning)';
    case 'LOW':
      return 'var(--color-success)';
    default:
      return 'rgba(255,255,255,0.4)';
  }
}

export type StatusKey = 'success' | 'fail' | 'rejected' | 'escalate' | 'pending' | 'pass' | string;

/** Recovery/phase 결과 → pill 클래스 */
export function statusToPill(status: StatusKey): string {
  switch (status) {
    case 'success':
    case 'pass':
      return 'pill-success';
    case 'fail':
      return 'pill-danger';
    case 'rejected':
    case 'escalate':
      return 'pill-warning';
    case 'pending':
    default:
      return 'bg-white/10 text-white/50';
  }
}

/** Phase 진행 상태 → 마커 색상 (SVG/dot 용) */
export function phaseStatusToColor(status: StatusKey): string {
  switch (status) {
    case 'success':
    case 'pass':
      return 'rgba(52, 211, 153, 0.7)'; // emerald
    case 'fail':
      return 'rgba(251, 113, 133, 0.7)'; // rose
    case 'rejected':
    case 'escalate':
      return 'rgba(251, 191, 36, 0.7)'; // amber
    case 'pending':
    default:
      return 'rgba(255, 255, 255, 0.1)';
  }
}

/** SLI 위반 여부 → pill 클래스 */
export function violationPill(violated: boolean): string {
  return violated ? 'pill-danger' : 'pill-success';
}

/** Yield 비교 임계 → ok/warn 클래스 (text 색상) */
export function yieldStatusText(yieldVal: number, target = 0.99): string {
  return yieldVal >= target ? 'text-emerald-300' : 'text-rose-300';
}

/** Severity 단축 라벨 (UI에서 1글자 배지용) */
export function severityShort(sev: SeverityKey): string {
  switch (sev) {
    case 'CRITICAL':
      return 'C';
    case 'HIGH':
      return 'H';
    case 'MEDIUM':
      return 'M';
    case 'LOW':
      return 'L';
    default:
      return '?';
  }
}
