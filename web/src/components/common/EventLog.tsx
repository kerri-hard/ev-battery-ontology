'use client';

import { useEffect, useRef } from 'react';
import { useEngine } from '@/context/EngineContext';
import Badge from '@/components/common/Badge';

export default function EventLog() {
  const { state } = useEngine();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.eventLog.length]);

  return (
    <div>
      <h3 className="text-xs text-text-dim mb-2 font-medium">이벤트 로그</h3>
      <div className="max-h-[400px] overflow-y-auto space-y-1">
        {state.eventLog.map((entry, i) => (
          <div key={i} className="flex items-start gap-1.5 text-xs leading-relaxed animate-fade-in">
            <span className="font-mono text-text-dim whitespace-nowrap">
              [{entry.ts}]
            </span>
            {entry.phase && <Badge phase={entry.phase} />}
            <span className="text-text-primary">{entry.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
