/**
 * Audio WebSocket hook — connects to the Python backend's /ws/audio endpoint
 * with JWT auth, parses incoming server events, and exposes typed control methods.
 */

import { useCallback, useEffect, useRef } from 'react';
import { useSyncExternalStore } from 'react';
import { ReconnectingSocket, type SocketStatus } from './reconnecting-socket';
import { getWsUrl, getAuthToken } from './config';

// ---------------------------------------------------------------------------
// Server event types
// ---------------------------------------------------------------------------
export type ServerEvent = {
  event: string;
  data: Record<string, unknown>;
};

export type EventHandler = (event: ServerEvent) => void;

// ---------------------------------------------------------------------------
// Module-level singleton state
// ---------------------------------------------------------------------------
let socket: ReconnectingSocket | null = null;
let currentStatus: SocketStatus = 'idle';
let currentSessionId: string | null = null;
const statusListeners = new Set<() => void>();
const eventHandlers = new Set<EventHandler>();

function notifyStatus() {
  statusListeners.forEach((l) => l());
}

function buildUrl(sessionId?: string | null): string {
  const base = getWsUrl();
  const token = getAuthToken();
  const params = new URLSearchParams();
  if (token) params.set('token', token);
  if (sessionId) params.set('session_id', sessionId);
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

function handleMessage(raw: string | ArrayBuffer) {
  if (typeof raw !== 'string') return;
  try {
    const msg = JSON.parse(raw) as ServerEvent;
    // Capture session ID from session events
    if (msg.event === 'session' && msg.data?.session_id) {
      currentSessionId = msg.data.session_id as string;
      notifyStatus();
    }
    eventHandlers.forEach((h) => h(msg));
  } catch {
    // ignore malformed messages
  }
}

function getOrCreateSocket(sessionId?: string | null): ReconnectingSocket {
  if (!socket) {
    socket = new ReconnectingSocket({
      url: buildUrl(sessionId),
      lazy: true,
      onStatusChange: (s) => {
        currentStatus = s;
        notifyStatus();
      },
      onMessage: handleMessage,
    });
  }
  return socket;
}

function destroySocket() {
  if (socket) {
    socket.dispose();
    socket = null;
    currentStatus = 'idle';
    currentSessionId = null;
    notifyStatus();
  }
}

// ---------------------------------------------------------------------------
// useSyncExternalStore integration
// ---------------------------------------------------------------------------
function subscribe(listener: () => void) {
  statusListeners.add(listener);
  return () => {
    statusListeners.delete(listener);
  };
}

function getStatusSnapshot(): SocketStatus {
  return currentStatus;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------
export function useAudioSocket() {
  const status = useSyncExternalStore(subscribe, getStatusSnapshot, getStatusSnapshot);

  // Event subscription — register handler on mount, remove on unmount
  const handlerRef = useRef<EventHandler | null>(null);

  const onEvent = useCallback((handler: EventHandler) => {
    // Remove previous handler if any
    if (handlerRef.current) {
      eventHandlers.delete(handlerRef.current);
    }
    handlerRef.current = handler;
    eventHandlers.add(handler);
    return () => {
      eventHandlers.delete(handler);
      handlerRef.current = null;
    };
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (handlerRef.current) {
        eventHandlers.delete(handlerRef.current);
        handlerRef.current = null;
      }
    };
  }, []);

  const connect = useCallback((sessionId?: string | null) => {
    // Tear down existing connection if URL would change
    if (socket) {
      destroySocket();
    }
    const sock = getOrCreateSocket(sessionId);
    sock.connect();
  }, []);

  const disconnect = useCallback(() => {
    destroySocket();
  }, []);

  const sendJSON = useCallback((obj: Record<string, unknown>) => {
    const sock = getOrCreateSocket();
    sock.send(JSON.stringify(obj));
  }, []);

  const sendBinary = useCallback((data: ArrayBuffer) => {
    const sock = getOrCreateSocket();
    sock.sendBinary(data);
  }, []);

  // Typed control methods
  const sendStart = useCallback(() => sendJSON({ type: 'start' }), [sendJSON]);
  const sendStop = useCallback(() => sendJSON({ type: 'stop' }), [sendJSON]);
  const sendCancel = useCallback(() => sendJSON({ type: 'cancel' }), [sendJSON]);
  const sendInterrupt = useCallback(() => sendJSON({ type: 'interrupt' }), [sendJSON]);
  const sendInit = useCallback(() => sendJSON({ type: 'init' }), [sendJSON]);

  return {
    status,
    sessionId: currentSessionId,
    connect,
    disconnect,
    sendBinary,
    sendJSON,
    sendStart,
    sendStop,
    sendCancel,
    sendInterrupt,
    sendInit,
    onEvent,
  };
}
