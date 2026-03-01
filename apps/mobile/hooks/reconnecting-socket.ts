export type SocketStatus = 'idle' | 'connecting' | 'connected' | 'disconnected';

export type ReconnectingSocketOptions = {
  url: string;
  initialBackoff?: number;
  maxBackoff?: number;
  /** If true, starts in 'idle' and waits for explicit connect(). Default: false (auto-connects). */
  lazy?: boolean;
  onStatusChange?: (status: SocketStatus) => void;
  onMessage?: (data: string | ArrayBuffer) => void;
  onOpen?: () => void;
  onClose?: () => void;
};

export class ReconnectingSocket {
  private url: string;
  private initialBackoff: number;
  private maxBackoff: number;
  private backoff: number;
  private ws: WebSocket | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;
  private shouldReconnect = true;

  private onStatusChange?: (status: SocketStatus) => void;
  private onMessage?: (data: string | ArrayBuffer) => void;
  private onOpen?: () => void;
  private onClose?: () => void;

  status: SocketStatus;

  constructor(opts: ReconnectingSocketOptions) {
    this.url = opts.url;
    this.initialBackoff = opts.initialBackoff ?? 1000;
    this.maxBackoff = opts.maxBackoff ?? 30_000;
    this.backoff = this.initialBackoff;
    this.onStatusChange = opts.onStatusChange;
    this.onMessage = opts.onMessage;
    this.onOpen = opts.onOpen;
    this.onClose = opts.onClose;

    if (opts.lazy) {
      this.status = 'idle';
      this.shouldReconnect = false;
    } else {
      this.status = 'idle';
      this.connect();
    }
  }

  private setStatus(s: SocketStatus) {
    this.status = s;
    this.onStatusChange?.(s);
  }

  connect() {
    if (this.disposed) return;
    if (this.status === 'connected' || this.status === 'connecting') return;

    this.shouldReconnect = true;
    this.clearTimer();
    this.openSocket();
  }

  disconnect() {
    this.shouldReconnect = false;
    this.clearTimer();
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  dispose() {
    this.disposed = true;
    this.disconnect();
  }

  send(data: string) {
    if (!this.ws || this.status !== 'connected') {
      throw new Error('Socket is not connected');
    }
    this.ws.send(data);
  }

  sendBinary(data: ArrayBuffer) {
    if (!this.ws || this.status !== 'connected') {
      throw new Error('Socket is not connected');
    }
    this.ws.send(data);
  }

  private openSocket() {
    if (this.disposed) return;
    this.setStatus('connecting');
    console.log(`[ReconnectingSocket] connecting to ${this.url.replace(/token=[^&]+/, 'token=***')}`);

    const ws = new WebSocket(this.url);
    ws.binaryType = 'arraybuffer';
    this.ws = ws;

    ws.onopen = () => {
      if (this.disposed) { ws.close(); return; }
      this.backoff = this.initialBackoff;
      this.setStatus('connected');
      console.log('[ReconnectingSocket] connected');
      this.onOpen?.();
    };

    ws.onclose = (ev) => {
      if (this.disposed) return;
      this.ws = null;
      console.log(`[ReconnectingSocket] closed  code=${ev.code}  reason=${ev.reason}`);
      this.setStatus('disconnected');
      this.onClose?.();
      this.scheduleReconnect();
    };

    ws.onerror = (ev) => {
      if (this.disposed) return;
      console.warn('[ReconnectingSocket] error:', ev);
      ws.close();
    };

    ws.onmessage = (event) => {
      this.onMessage?.(event.data);
    };
  }

  private scheduleReconnect() {
    if (!this.shouldReconnect || this.disposed) return;
    const delay = this.backoff;
    this.backoff = Math.min(this.backoff * 2, this.maxBackoff);
    this.timer = setTimeout(() => this.openSocket(), delay);
  }

  private clearTimer() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
