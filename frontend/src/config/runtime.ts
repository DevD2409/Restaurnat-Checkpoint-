/**
 * Runtime & build-time backend endpoint resolution.
 *
 * Resolution order:
 * 1. Vite build-time env vars (VITE_API_URL / VITE_WS_URL)
 * 2. Optional public /runtime-config.js (window.__SRMP_CONFIG__)
 * 3. Development-only localhost fallback (stripped from production builds)
 * 4. Neutral production fallback ('/api/v1' for REST, '' to skip WS until configured)
 */

interface RuntimeConfigShape {
  VITE_API_URL?: string;
  VITE_WS_URL?: string;
}

declare global {
  interface Window {
    __SRMP_CONFIG__?: RuntimeConfigShape;
  }
}

let hasWarnedMissingBackend = false;

function readConfiguredValue(key: keyof RuntimeConfigShape): string {
  const buildTimeValue = (import.meta.env[key] as string | undefined)?.trim();
  if (buildTimeValue) {
    return buildTimeValue;
  }
  if (typeof window !== 'undefined') {
    const runtimeValue = window.__SRMP_CONFIG__?.[key]?.trim();
    if (runtimeValue) {
      return runtimeValue;
    }
  }
  return '';
}

function warnOnceIfUnconfigured(): void {
  if (import.meta.env.DEV || hasWarnedMissingBackend) {
    return;
  }
  hasWarnedMissingBackend = true;
  console.warn(
    '[SRMP] Backend URL is not configured yet. Set VITE_API_URL and VITE_WS_URL at build time (e.g. via frontend/.env.production.local) or configure /runtime-config.js once Render is deployed.'
  );
}

export function getApiBaseUrl(): string {
  const configured = readConfiguredValue('VITE_API_URL');
  if (configured) {
    return configured.replace(/\/+$/, '');
  }
  if (import.meta.env.DEV) {
    return 'http://localhost:8000/api/v1';
  }
  warnOnceIfUnconfigured();
  return '/api/v1';
}

export function getWsBaseUrl(): string {
  const configured = readConfiguredValue('VITE_WS_URL');
  if (configured) {
    return configured.replace(/\/+$/, '');
  }
  if (import.meta.env.DEV) {
    return 'ws://localhost:8000/ws';
  }
  warnOnceIfUnconfigured();
  return '';
}
