'use client';

interface ConnectionDotProps {
  status: 'connecting' | 'connected' | 'disconnected';
}

const statusStyles: Record<ConnectionDotProps['status'], string> = {
  connected: 'bg-[#06d6a0] shadow-[0_0_6px_rgba(6,214,160,0.5)]',
  disconnected: 'bg-[#f5576c] animate-pulse',
  connecting: 'bg-[#ffd166]',
};

export default function ConnectionDot({ status }: ConnectionDotProps) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${statusStyles[status]}`}
      title={status}
    />
  );
}
