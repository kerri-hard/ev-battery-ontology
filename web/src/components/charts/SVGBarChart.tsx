'use client';

interface SVGBarChartProps {
  items: { label: string; value: number; color?: string }[];
  maxValue?: number;
}

export default function SVGBarChart({ items, maxValue }: SVGBarChartProps) {
  const max = maxValue ?? Math.max(...items.map((it) => it.value), 1);

  if (items.length === 0) {
    return <div className="text-text-dim text-xs py-2">데이터 없음</div>;
  }

  return (
    <div className="space-y-1">
      {items.map((item) => {
        const pct = (item.value / max) * 100;
        const color = item.color || '#00d2ff';

        return (
          <div key={item.label} className="flex items-center gap-2">
            <span className="text-xs text-text-dim w-[100px] truncate">{item.label}</span>
            <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
              <div
                className="h-full rounded transition-all"
                style={{ width: `${pct}%`, backgroundColor: color }}
              />
            </div>
            <span className="text-xs font-mono text-text-primary w-10 text-right">
              {item.value}
            </span>
          </div>
        );
      })}
    </div>
  );
}
