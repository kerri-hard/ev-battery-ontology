const configuredBase = process.env.NEXT_PUBLIC_API_BASE?.trim();

function browserFallbackBase(): string {
  if (typeof window === 'undefined') return 'http://localhost:8080';
  const host = window.location.hostname || 'localhost';
  return `http://${host}:8080`;
}

export function apiUrl(path: string): string {
  const base = configuredBase || browserFallbackBase();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

export function wsUrl(path: string): string {
  const httpBase = configuredBase || browserFallbackBase();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  if (httpBase.startsWith('https://')) {
    return `wss://${httpBase.slice('https://'.length)}${normalizedPath}`;
  }
  if (httpBase.startsWith('http://')) {
    return `ws://${httpBase.slice('http://'.length)}${normalizedPath}`;
  }
  return `ws://${httpBase}${normalizedPath}`;
}

