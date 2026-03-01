/**
 * Server configuration — reads from Expo env vars.
 */

/** Base URL for REST API (e.g. http://192.168.1.42:8000) */
export function getApiBaseUrl(): string {
  return (
    process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '') ??
    'http://localhost:8000'
  );
}

/** WebSocket URL for audio endpoint */
export function getWsUrl(): string {
  const base = getApiBaseUrl();
  const wsBase = base.replace(/^http/, 'ws');
  return `${wsBase}/ws/audio`;
}

/** JWT auth token */
export function getAuthToken(): string {
  return process.env.EXPO_PUBLIC_JWT_TOKEN ?? '';
}

/** Authorization headers for REST calls */
export function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
