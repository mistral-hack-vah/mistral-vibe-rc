import { WebSocketServer, type WebSocket } from 'ws';
import type { IncomingMessage } from 'node:http';
import { createServer, type Server } from 'node:http';

export type MockServerOptions = {
  onConnection?: (ws: WebSocket, req: IncomingMessage) => void;
};

export class MockWSServer {
  private httpServer: Server;
  private wss: WebSocketServer;
  private _port = 0;
  clients: WebSocket[] = [];
  received: (string | Buffer)[] = [];

  constructor(opts: MockServerOptions = {}) {
    this.httpServer = createServer();
    this.wss = new WebSocketServer({ server: this.httpServer });

    this.wss.on('connection', (ws, req) => {
      this.clients.push(ws);
      ws.on('message', (data, isBinary) => {
        this.received.push(isBinary ? (data as Buffer) : data.toString());
      });
      ws.on('close', () => {
        this.clients = this.clients.filter((c) => c !== ws);
      });
      opts.onConnection?.(ws, req);
    });
  }

  get port() {
    return this._port;
  }

  get url() {
    return `ws://127.0.0.1:${this._port}`;
  }

  async start(): Promise<void> {
    return new Promise((resolve) => {
      this.httpServer.listen(0, '127.0.0.1', () => {
        const addr = this.httpServer.address();
        if (addr && typeof addr === 'object') this._port = addr.port;
        resolve();
      });
    });
  }

  async close(): Promise<void> {
    for (const ws of this.clients) ws.close();
    this.wss.close();
    return new Promise((resolve) => this.httpServer.close(() => resolve()));
  }

  /** Send a message to all connected clients */
  broadcast(data: string | Buffer) {
    for (const ws of this.clients) ws.send(data);
  }

  clear() {
    this.received = [];
  }
}
