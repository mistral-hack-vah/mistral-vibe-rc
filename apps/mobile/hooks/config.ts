/**
 * Server configuration — reads from runtime overrides first, then Expo env vars.
 */

// ---------------------------------------------------------------------------
// Runtime overrides (mutable, set via settings UI)
// ---------------------------------------------------------------------------
let runtimeHostname: string | null = null;
let runtimePort: number | null = null;

const configListeners = new Set<() => void>();

function notifyConfigChange() {
  configListeners.forEach((l) => l());
}

/** Subscribe to config changes. Returns unsubscribe function. */
export function onConfigChange(listener: () => void): () => void {
  configListeners.add(listener);
  return () => { configListeners.delete(listener); };
}

/** Update the server hostname and port at runtime. */
export function setServerConfig(hostname: string, port: number) {
  runtimeHostname = hostname;
  runtimePort = port;
  notifyConfigChange();
}

/** Get current server config (hostname, port). */
export function getServerConfig(): { hostname: string; port: number } {
  if (runtimeHostname !== null && runtimePort !== null) {
    return { hostname: runtimeHostname, port: runtimePort };
  }
  // Parse from env var or use defaults
  const envUrl = process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '') ?? '';
  if (envUrl) {
    try {
      const url = new URL(envUrl);
      return {
        hostname: url.hostname,
        port: url.port ? parseInt(url.port, 10) : 8000,
      };
    } catch {
      // fall through to defaults
    }
  }
  return { hostname: 'localhost', port: 8000 };
}

// ---------------------------------------------------------------------------
// Derived URLs
// ---------------------------------------------------------------------------

/** Base URL for REST API (e.g. http://192.168.1.42:8000) */
export function getApiBaseUrl(): string {
  if (runtimeHostname !== null && runtimePort !== null) {
    return `http://${runtimeHostname}:${runtimePort}`;
  }
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
