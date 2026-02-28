import { useSyncExternalStore } from 'react';
import { ReconnectingSocket, type SocketStatus } from './reconnecting-socket';

const WS_URL = 'ws://localhost:14096/ws/control';

let socket: ReconnectingSocket | null = null;
let currentStatus: SocketStatus = 'idle';
const listeners = new Set<() => void>();

function getSocket(): ReconnectingSocket {
  if (!socket) {
    socket = new ReconnectingSocket({
      url: WS_URL,
      lazy: false,
      onStatusChange: (s) => {
        currentStatus = s;
        listeners.forEach((l) => l());
      },
    });
  }
  return socket;
}

function subscribe(listener: () => void) {
  // Ensure socket is created on first subscription
  getSocket();
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot() {
  return currentStatus;
}

export type ConnectionStatus = SocketStatus;

export function useControlSocket() {
  const status = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  return {
    status,
    reconnect: () => getSocket().connect(),
  };
}
