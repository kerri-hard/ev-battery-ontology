import type { Area, L3TrendHistory } from './types';

export const AREAS: Area[] = [
  { id: 'PA-100', name: '셀 어셈블리', color: '#FF6B35', icon: '⚡' },
  { id: 'PA-200', name: '전장 조립', color: '#00B4D8', icon: '🔌' },
  { id: 'PA-300', name: '냉각 시스템', color: '#10b981', icon: '❄' },
  { id: 'PA-400', name: '인클로저', color: '#ef4444', icon: '🛡' },
  { id: 'PA-500', name: '최합조립/검사', color: '#f59e0b', icon: '✓' },
];

export const L3_RELATION_TYPES = ['MATCHED_BY', 'CHAIN_USES', 'HAS_CAUSE', 'HAS_PATTERN'];
export const MAX_L3_TREND = 30;

export const EMPTY_L3_TREND: L3TrendHistory = {
  causes: [],
  matchedBy: [],
  chainUses: [],
  hasCause: [],
  hasPattern: [],
};

export function yieldColor(y: number): string {
  if (y >= 0.995) return '#10b981';
  if (y >= 0.99) return '#f59e0b';
  return '#ef4444';
}

export function autoLabel(a: string): { text: string; color: string } {
  if (a === '자동') return { text: 'AUTO', color: '#10b981' };
  if (a === '반자동') return { text: 'SEMI', color: '#f59e0b' };
  return { text: 'MANUAL', color: '#ef4444' };
}

export function clamp(num: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, num));
}
