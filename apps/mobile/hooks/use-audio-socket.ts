import { useSyncExternalStore } from 'react';
import { ReconnectingSocket, type SocketStatus } from './reconnecting-socket';

const WS_URL = 'ws://localhost:14096/ws/audio';

let socket: ReconnectingSocket | null = null;
let currentStatus: SocketStatus = 'idle';
const listeners = new Set<() => void>();
const messageListeners = new Set<(data: string | ArrayBuffer) => void>();

function getSocket(): ReconnectingSocket {
  if (!socket) {
    socket = new ReconnectingSocket({
      url: WS_URL,
      lazy: true,
      onStatusChange: (s) => {
        currentStatus = s;
        listeners.forEach((l) => l());
      },
      onMessage: (data) => messageListeners.forEach((l) => l(data)),
    });
  }
  return socket;
}

function subscribe(listener: () => void) {
  getSocket();
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot() {
  return currentStatus;
}

export function useAudioSocket() {
  const status = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const sock = getSocket();

  return {
    status,
    connect: () => sock.connect(),
    disconnect: () => sock.disconnect(),
    reconnect: () => sock.connect(),
    sendBinary: (data: ArrayBuffer) => sock.sendBinary(data),
    sendJSON: (obj: Record<string, unknown>) => sock.send(JSON.stringify(obj)),
    subscribeMessages: (fn: (data: string | ArrayBuffer) => void) => {
      messageListeners.add(fn);
      return () => messageListeners.delete(fn);
    },
  };
}
