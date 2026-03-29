'use client';

interface Dataset {
  label: string;
  data: number[];
  color: string;
}

interface SVGLineChartProps {
  datasets: Dataset[];
  width?: number;
  height?: number;
}

export default function SVGLineChart({ datasets, width = 400, height = 200 }: SVGLineChartProps) {
  const padding = { top: 20, right: 20, bottom: 40, left: 50 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Compute global min/max across all datasets
  const allValues = datasets.flatMap((ds) => ds.data);
  if (allValues.length === 0) {
    return (
      <svg width={width} height={height}>
        <text x={width / 2} y={height / 2} fill="#8888aa" textAnchor="middle" fontSize={12}>
          데이터 없음
        </text>
      </svg>
    );
  }

  const rawMin = Math.min(...allValues);
  const rawMax = Math.max(...allValues);
  const range = rawMax - rawMin || 1;
  const yMin = rawMin - range * 0.05;
  const yMax = rawMax + range * 0.05;

  const maxLen = Math.max(...datasets.map((ds) => ds.data.length));

  function xScale(i: number): number {
    if (maxLen <= 1) return padding.left + chartW / 2;
    return padding.left + (i / (maxLen - 1)) * chartW;
  }

  function yScale(v: number): number {
    return padding.top + chartH - ((v - yMin) / (yMax - yMin)) * chartH;
  }

  // Grid lines (5 lines)
  const gridLines = Array.from({ length: 5 }, (_, i) => {
    const val = yMin + ((yMax - yMin) * i) / 4;
    return { y: yScale(val), label: val.toFixed(2) };
  });

  return (
    <svg width={width} height={height} className="overflow-visible">
      {/* Grid lines */}
      {gridLines.map((line, i) => (
        <g key={i}>
          <line
            x1={padding.left}
            y1={line.y}
            x2={padding.left + chartW}
            y2={line.y}
            stroke="#ffffff10"
            strokeDasharray="3,3"
          />
          <text
            x={padding.left - 6}
            y={line.y + 3}
            fill="#8888aa"
            fontSize={9}
            textAnchor="end"
            fontFamily="monospace"
          >
            {line.label}
          </text>
        </g>
      ))}

      {/* X-axis labels */}
      {Array.from({ length: maxLen }, (_, i) => (
        <text
          key={i}
          x={xScale(i)}
          y={padding.top + chartH + 14}
          fill="#8888aa"
          fontSize={9}
          textAnchor="middle"
          fontFamily="monospace"
        >
          {i}
        </text>
      ))}

      {/* Dataset polylines + markers */}
      {datasets.map((ds) => {
        if (ds.data.length === 0) return null;

        const points = ds.data.map((v, i) => `${xScale(i)},${yScale(v)}`).join(' ');

        return (
          <g key={ds.label}>
            <polyline
              points={points}
              fill="none"
              stroke={ds.color}
              strokeWidth={1.5}
              strokeLinejoin="round"
            />
            {ds.data.map((v, i) => (
              <circle
                key={i}
                cx={xScale(i)}
                cy={yScale(v)}
                r={2.5}
                fill={ds.color}
                stroke="#0a0a1a"
                strokeWidth={1}
              />
            ))}
          </g>
        );
      })}

      {/* Legend */}
      {datasets.map((ds, idx) => {
        const lx = padding.left + idx * 100;
        const ly = height - 6;
        return (
          <g key={ds.label}>
            <circle cx={lx} cy={ly} r={4} fill={ds.color} />
            <text x={lx + 8} y={ly + 3} fill="#8888aa" fontSize={10}>
              {ds.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
