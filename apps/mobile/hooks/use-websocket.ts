import { useEffect, useRef, useState } from 'react';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

const WS_URL = 'ws://localhost:14096/ws';
const MAX_BACKOFF = 30_000;

export function useWebSocket() {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(1000);

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;
      setStatus('connecting');

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmounted) return;
        backoffRef.current = 1000;
        setStatus('connected');
      };

      ws.onclose = () => {
        if (unmounted) return;
        setStatus('disconnected');
        scheduleReconnect();
      };

      ws.onerror = () => {
        if (unmounted) return;
        ws.close();
      };
    }

    function scheduleReconnect() {
      if (unmounted) return;
      const delay = backoffRef.current;
      backoffRef.current = Math.min(delay * 2, MAX_BACKOFF);
      timerRef.current = setTimeout(connect, delay);
    }

    connect();

    return () => {
      unmounted = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, []);

  return status;
}
