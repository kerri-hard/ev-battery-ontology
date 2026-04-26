'use client';

import { createContext, useContext } from 'react';
import type { EngineState, WSCommand } from '@/types';
import { useHarnessEngine } from '@/hooks/useHarnessEngine';

interface EngineContextValue {
  state: EngineState;
  sendCommand: (cmd: WSCommand) => void;
  selectIncident: (id: string | null) => void;
}

const EngineContext = createContext<EngineContextValue | null>(null);

export function EngineProvider({ children }: { children: React.ReactNode }) {
  const engine = useHarnessEngine();
  return <EngineContext.Provider value={engine}>{children}</EngineContext.Provider>;
}

export function useEngine() {
  const ctx = useContext(EngineContext);
  if (!ctx) throw new Error('useEngine must be used within EngineProvider');
  return ctx;
}
