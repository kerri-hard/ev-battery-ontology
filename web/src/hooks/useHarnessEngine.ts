'use client';

import { useReducer, useEffect, useRef, useCallback } from 'react';
import type { EngineState, WSCommand } from '@/types';
import { wsUrl } from '@/lib/api';
import { eventHandlers } from './reducers';

const initialState: EngineState = {
  connectionStatus: 'connecting',
  iteration: 0,
  maxIterations: 10,
  running: false,
  paused: false,
  speed: 1.0,
  metrics: null,
  prevMetrics: null,
  initialMetrics: null,
  agents: [],
  skills: {},
  history: [],
  graphData: null,
  steps: [],
  currentPhase: null,
  debate: { proposals: null, votes: null, applied: null, evaluation: null, learning: null },
  eventLog: [],
  metricsHistory: { nodes: [], edges: [], yield: [], completeness: [] },
  latestAnalysis: null,
  correlations: [],
  healing: {
    iteration: 0,
    running: false,
    incidents: 0,
    autoRecovered: 0,
    recentIncidents: [],
    recurrenceKpis: {
      matched_chain_rate: 0,
      repeat_incident_rate: 0,
      matched_auto_recovery_rate: 0,
      matched_avg_recovery_sec: 0,
      unmatched_avg_recovery_sec: 0,
      total: 0,
    },
    hitlPending: [],
    hitlAudit: [],
    hitlPolicy: { min_confidence: 0.62, high_risk_threshold: 0.6, medium_requires_history: true },
  },
  healingPhase: null,
  phase4: {
    predictive_agent: false,
    nl_diagnoser: false,
    llm_orchestrator: false,
    model: 'none',
    latest_predictive: [],
    orchestrator_traces: [],
  },
  selectedIncidentId: null,
  currentView: 'healing',
};

type Action =
  | { type: 'SET_CONNECTED' }
  | { type: 'SET_DISCONNECTED' }
  | { type: 'SELECT_INCIDENT'; id: string | null }
  | { type: 'SET_VIEW'; view: import('@/types').ViewKey }
  | { type: 'WS_EVENT'; event: string; data: Record<string, unknown> };

function reducer(state: EngineState, action: Action): EngineState {
  switch (action.type) {
    case 'SET_CONNECTED':
      return { ...state, connectionStatus: 'connected' };
    case 'SET_DISCONNECTED':
      return { ...state, connectionStatus: 'disconnected' };
    case 'SELECT_INCIDENT':
      return { ...state, selectedIncidentId: action.id };
    case 'SET_VIEW':
      return { ...state, currentView: action.view };
    case 'WS_EVENT': {
      const handler = eventHandlers[action.event];
      return handler ? handler(state, action.data) : state;
    }
    default:
      return state;
  }
}

export function useHarnessEngine() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(wsUrl('/ws'));
    wsRef.current = ws;

    ws.onopen = () => dispatch({ type: 'SET_CONNECTED' });

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        dispatch({ type: 'WS_EVENT', event: msg.event, data: msg.data || {} });
      } catch { /* ignore parse errors */ }
    };

    ws.onclose = () => {
      dispatch({ type: 'SET_DISCONNECTED' });
      reconnectRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendCommand = useCallback((cmd: WSCommand) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  const selectIncident = useCallback((id: string | null) => {
    dispatch({ type: 'SELECT_INCIDENT', id });
  }, []);

  const setView = useCallback((view: import('@/types').ViewKey) => {
    dispatch({ type: 'SET_VIEW', view });
  }, []);

  return { state, sendCommand, selectIncident, setView };
}
