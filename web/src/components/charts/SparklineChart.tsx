'use client';

interface SparklineChartProps {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}

export default function SparklineChart({
  data,
  color,
  width = 100,
  height = 28,
}: SparklineChartProps) {
  if (data.length === 0) {
    return <svg width={width} height={height} />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const padding = 2;
  const innerW = width - padding * 2;
  const innerH = height - padding * 2;

  const points = data.map((v, i) => {
    const x = padding + (data.length > 1 ? (i / (data.length - 1)) * innerW : innerW / 2);
    const y = padding + innerH - ((v - min) / range) * innerH;
    return `${x},${y}`;
  });

  const lastPoint = points[points.length - 1];
  const [lx, ly] = lastPoint.split(',').map(Number);

  return (
    <svg width={width} height={height} className="block">
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.8}
      />
      <circle cx={lx} cy={ly} r={2.5} fill={color} />
    </svg>
  );
}
