'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { StepPosition } from './types';

interface PositionTracker {
  graphBodyRef: React.RefObject<HTMLDivElement>;
  registerStepRef: (stepId: string) => (el: HTMLDivElement | null) => void;
  stepPositions: Map<string, StepPosition>;
}

/** Step 카드 위치를 추적하여 SVG 엣지 오버레이가 정확히 그려지도록 한다. */
export function useStepPositions(stepCount: number): PositionTracker {
  const graphBodyRef = useRef<HTMLDivElement>(null) as React.MutableRefObject<HTMLDivElement | null>;
  const stepRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const [stepPositions, setStepPositions] = useState<Map<string, StepPosition>>(new Map());

  const registerStepRef = useCallback(
    (stepId: string) => (el: HTMLDivElement | null) => {
      if (el) stepRefs.current.set(stepId, el);
      else stepRefs.current.delete(stepId);
    },
    [],
  );

  const measure = useCallback(() => {
    const container = graphBodyRef.current;
    if (!container) return;
    const cRect = container.getBoundingClientRect();
    const positions = new Map<string, StepPosition>();
    stepRefs.current.forEach((el, id) => {
      const r = el.getBoundingClientRect();
      const left = r.left - cRect.left;
      const top = r.top - cRect.top;
      positions.set(id, {
        left,
        top,
        width: r.width,
        height: r.height,
        cx: left + r.width / 2,
        cy: top + r.height / 2,
      });
    });
    setStepPositions(positions);
  }, []);

  useEffect(() => {
    if (stepCount === 0 || !graphBodyRef.current) return;
    let raf = 0;
    const requestMeasure = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(measure);
    };
    requestMeasure();

    const container = graphBodyRef.current;
    const onResize = () => requestMeasure();
    window.addEventListener('resize', onResize);
    container.addEventListener('scroll', requestMeasure, true);

    const ro = new ResizeObserver(() => requestMeasure());
    ro.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      container.removeEventListener('scroll', requestMeasure, true);
      ro.disconnect();
    };
  }, [stepCount, measure]);

  return {
    graphBodyRef: graphBodyRef as React.RefObject<HTMLDivElement>,
    registerStepRef,
    stepPositions,
  };
}
