'use client';

interface TrustBarProps {
  trust: number;
  maxTrust?: number;
}

export default function TrustBar({ trust = 1.0, maxTrust = 1.5 }: TrustBarProps) {
  const t = trust ?? 1.0;
  const pct = Math.min((t / maxTrust) * 100, 100);

  let colorClass = 'bg-neon-red';
  if (t > 1.1) colorClass = 'bg-neon-green';
  else if (t >= 0.8) colorClass = 'bg-neon-yellow';

  return (
    <div className="w-[60px] h-1.5 rounded-full bg-white/10 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ${colorClass}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
