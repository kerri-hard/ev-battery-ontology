'use client';

import { useState } from 'react';
import { apiUrl } from '@/lib/api';
import GlassCard from '@/components/common/GlassCard';

interface NLQueryResult {
  question: string;
  cypher: string;
  explain: string;
  blocked: boolean;
  block_reason: string | null;
  warnings: string[];
  executed: boolean;
  rows: string[][];
  source: 'llm' | 'fallback' | 'none';
}

const EXAMPLE_QUESTIONS = [
  'yield 0.99 미만 step 모두 보여줘',
  'PS-203 와이어 하네스의 결함 모드는?',
  '최근 incident에서 가장 많이 나온 root cause top 3',
  'EQUIPMENT_RESET이 성공한 사례 모두',
];

/** Console NL Query — 자연어 → 안전 read-only Cypher 변환 + 선택적 실행.
 *
 *  가드레일은 backend (`nl2cypher.py`) 에 있다. 본 UI는 입력/결과만 담당.
 *  - dry-run (Cypher만): execute=false
 *  - 실행 (rows 반환): execute=true (가드 통과 시)
 */
export default function NLQuery() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<NLQueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [execute, setExecute] = useState(false);

  async function submit() {
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await fetch(apiUrl('/api/nl-query'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, execute }),
      });
      const data = (await r.json()) as NLQueryResult;
      setResult(data);
    } catch (e) {
      setResult({
        question,
        cypher: '',
        explain: '',
        blocked: true,
        block_reason: `network_error:${String(e)}`,
        warnings: [],
        executed: false,
        rows: [],
        source: 'none',
      });
    } finally {
      setLoading(false);
    }
  }

  function fillExample(q: string) {
    setQuestion(q);
  }

  return (
    <GlassCard className="p-3">
      <div className="ds-label mb-2">🔎 자연어 그래프 질의 — read-only 가드레일</div>

      <div className="flex gap-2 mb-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="예: yield 0.99 미만 step 보여줘"
          className="flex-1 ds-body bg-white/5 border border-white/10 rounded px-2 py-1 focus:outline-none focus:border-cyan-400/40"
          aria-label="자연어 질문 입력"
        />
        <label className="flex items-center gap-1 ds-caption text-white/60 select-none">
          <input
            type="checkbox"
            checked={execute}
            onChange={(e) => setExecute(e.target.checked)}
            aria-label="실행 모드"
          />
          실행
        </label>
        <button
          onClick={submit}
          disabled={loading || !question.trim()}
          className="px-3 py-1 rounded pill-info hover:opacity-90 transition ds-body font-bold disabled:opacity-50"
          aria-label="질문 전송"
        >
          {loading ? '...' : '전송'}
        </button>
      </div>

      <div className="ds-caption text-white/50 mb-2">
        예시:{' '}
        {EXAMPLE_QUESTIONS.map((q, i) => (
          <button
            key={i}
            onClick={() => fillExample(q)}
            className="underline decoration-dotted hover:text-cyan-300 mr-2"
          >
            {q}
          </button>
        ))}
      </div>

      {result && (
        <div className="mt-2 space-y-2">
          {/* 차단 사유 */}
          {result.blocked && (
            <div className="pill-danger ds-caption px-2 py-1.5 rounded">
              🛑 차단: {result.block_reason}
              {result.source === 'fallback' && ' (LLM 미설정 — OPENAI_API_KEY 필요)'}
            </div>
          )}

          {/* 변환된 Cypher */}
          {result.cypher && (
            <div className="bg-black/30 border border-white/10 rounded p-2">
              <div className="ds-caption text-white/50 mb-1">
                Cypher{' '}
                <span className="text-cyan-300">[{result.source}]</span>
                {result.warnings.length > 0 && (
                  <span className="text-amber-300 ml-2">
                    ⚠ {result.warnings.join(', ')}
                  </span>
                )}
              </div>
              <pre className="ds-body font-mono text-cyan-100 whitespace-pre-wrap break-all">
                {result.cypher}
              </pre>
              {result.explain && (
                <div className="ds-caption text-white/60 mt-1">{result.explain}</div>
              )}
            </div>
          )}

          {/* 실행 결과 (rows) */}
          {result.executed && (
            <div className="bg-black/30 border border-white/10 rounded p-2">
              <div className="ds-caption text-white/50 mb-1">
                결과 ({result.rows.length} rows)
              </div>
              {result.rows.length === 0 ? (
                <div className="ds-caption text-white/40">(빈 결과)</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="ds-caption font-mono">
                    <tbody>
                      {result.rows.slice(0, 50).map((row, i) => (
                        <tr key={i} className="border-b border-white/5">
                          {row.map((cell, j) => (
                            <td key={j} className="px-2 py-0.5 text-white/80">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* dry-run 안내 */}
          {!result.blocked && !result.executed && result.cypher && (
            <div className="ds-caption text-white/50">
              💡 dry-run 모드 — 실행하려면 "실행" 체크 후 다시 전송
            </div>
          )}
        </div>
      )}
    </GlassCard>
  );
}
