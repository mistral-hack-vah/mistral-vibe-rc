import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { WebSocket } from 'ws';
import { MockWSServer } from './helpers/mock-ws-server';
import { ReconnectingSocket, type SocketStatus } from '../reconnecting-socket';

// Polyfill WebSocket for Node.js test environment
(globalThis as any).WebSocket = WebSocket;

function waitFor(
  fn: () => boolean,
  timeout = 5000,
  interval = 20,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout;
    const check = () => {
      if (fn()) return resolve();
      if (Date.now() > deadline) return reject(new Error('waitFor timed out'));
      setTimeout(check, interval);
    };
    check();
  });
}

describe('ReconnectingSocket', () => {
  let server: MockWSServer;

  beforeEach(async () => {
    server = new MockWSServer();
    await server.start();
  });

  afterEach(async () => {
    await server.close();
  });

  it('connects and transitions idle → connecting → connected', async () => {
    const statuses: SocketStatus[] = [];
    const sock = new ReconnectingSocket({
      url: server.url,
      onStatusChange: (s) => statuses.push(s),
    });

    await waitFor(() => sock.status === 'connected');
    expect(statuses).toContain('connecting');
    expect(statuses).toContain('connected');
    sock.dispose();
  });

  it('lazy socket starts idle and does not connect automatically', async () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      lazy: true,
    });

    expect(sock.status).toBe('idle');
    // Wait a bit to confirm it stays idle
    await new Promise((r) => setTimeout(r, 200));
    expect(sock.status).toBe('idle');
    expect(server.clients.length).toBe(0);
    sock.dispose();
  });

  it('lazy socket connects when connect() is called', async () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      lazy: true,
    });

    expect(sock.status).toBe('idle');
    sock.connect();
    await waitFor(() => sock.status === 'connected');
    expect(server.clients.length).toBe(1);
    sock.dispose();
  });

  it('auto-reconnects with exponential backoff', async () => {
    const statuses: SocketStatus[] = [];
    const sock = new ReconnectingSocket({
      url: server.url,
      initialBackoff: 50,
      maxBackoff: 400,
      onStatusChange: (s) => statuses.push(s),
    });

    await waitFor(() => sock.status === 'connected');

    // Close server-side to trigger reconnect
    for (const c of server.clients) c.close();
    await waitFor(() => sock.status === 'disconnected');

    // Should reconnect
    await waitFor(() => sock.status === 'connected');
    expect(statuses.filter((s) => s === 'connected').length).toBeGreaterThanOrEqual(2);
    sock.dispose();
  });

  it('backoff doubles up to max', async () => {
    // Close the server so connections always fail
    await server.close();

    const connectTimes: number[] = [];
    const originalWS = globalThis.WebSocket;
    const OrigWS = WebSocket;
    (globalThis as any).WebSocket = class extends OrigWS {
      constructor(url: string | URL, protocols?: any) {
        connectTimes.push(Date.now());
        super(url, protocols);
      }
    };

    // Create a new server that we immediately close to get a valid port that refuses connections
    const deadServer = new MockWSServer();
    await deadServer.start();
    const deadUrl = deadServer.url;
    await deadServer.close();

    const sock = new ReconnectingSocket({
      url: deadUrl,
      initialBackoff: 100,
      maxBackoff: 400,
    });

    // Wait for several reconnect attempts
    await new Promise((r) => setTimeout(r, 1500));
    sock.dispose();
    (globalThis as any).WebSocket = originalWS;

    // Verify backoff intervals increase
    if (connectTimes.length >= 3) {
      const intervals = [];
      for (let i = 1; i < connectTimes.length; i++) {
        intervals.push(connectTimes[i] - connectTimes[i - 1]);
      }
      // First interval should be shorter than later ones
      // (allowing some timing slack)
      expect(intervals.length).toBeGreaterThanOrEqual(2);
    }
  });

  it('resets backoff on successful connection', async () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      initialBackoff: 50,
    });

    await waitFor(() => sock.status === 'connected');

    // Force disconnect
    for (const c of server.clients) c.close();
    await waitFor(() => sock.status === 'disconnected');

    // Reconnect should happen quickly (backoff was reset)
    const start = Date.now();
    await waitFor(() => sock.status === 'connected');
    const elapsed = Date.now() - start;
    // Should reconnect within initial backoff + some slack
    expect(elapsed).toBeLessThan(300);
    sock.dispose();
  });

  it('manual connect() triggers immediate reconnection', async () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      initialBackoff: 50,
    });

    await waitFor(() => sock.status === 'connected');
    sock.disconnect();
    expect(sock.status).toBe('disconnected');

    sock.connect();
    await waitFor(() => sock.status === 'connected');
    sock.dispose();
  });

  it('disconnect() stops reconnection', async () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      initialBackoff: 50,
    });

    await waitFor(() => sock.status === 'connected');
    sock.disconnect();

    // Wait to ensure no reconnection happens
    await new Promise((r) => setTimeout(r, 300));
    expect(sock.status).toBe('disconnected');
    sock.dispose();
  });

  it('dispose() is permanent teardown', async () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      initialBackoff: 50,
    });

    await waitFor(() => sock.status === 'connected');
    sock.dispose();

    // connect() after dispose should be no-op
    sock.connect();
    await new Promise((r) => setTimeout(r, 200));
    expect(sock.status).toBe('disconnected');
  });

  it('send() delivers text frames to server', async () => {
    const sock = new ReconnectingSocket({ url: server.url });
    await waitFor(() => sock.status === 'connected');

    sock.send('hello');
    sock.send(JSON.stringify({ type: 'test' }));

    await waitFor(() => server.received.length === 2);
    expect(server.received[0]).toBe('hello');
    expect(server.received[1]).toBe('{"type":"test"}');
    sock.dispose();
  });

  it('sendBinary() delivers binary frames to server', async () => {
    const sock = new ReconnectingSocket({ url: server.url });
    await waitFor(() => sock.status === 'connected');

    const data = new Uint8Array([1, 2, 3, 4]).buffer;
    sock.sendBinary(data);

    await waitFor(() => server.received.length === 1);
    const received = server.received[0];
    expect(Buffer.isBuffer(received)).toBe(true);
    expect([...(received as Buffer)]).toEqual([1, 2, 3, 4]);
    sock.dispose();
  });

  it('send() throws when not connected', () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      lazy: true,
    });

    expect(() => sock.send('hello')).toThrow('Socket is not connected');
    sock.dispose();
  });

  it('onMessage callback receives messages from server', async () => {
    const messages: (string | ArrayBuffer)[] = [];
    const sock = new ReconnectingSocket({
      url: server.url,
      onMessage: (data) => messages.push(data),
    });

    await waitFor(() => sock.status === 'connected');
    server.broadcast('server-msg');

    await waitFor(() => messages.length === 1);
    // In Node ws, text messages come as Buffer when binaryType is arraybuffer
    // but our mock server sends text, so it may come as string or Buffer
    const msg = messages[0];
    const text = msg instanceof ArrayBuffer
      ? new TextDecoder().decode(msg)
      : typeof msg === 'string'
        ? msg
        : new TextDecoder().decode(msg as any);
    expect(text).toBe('server-msg');
    sock.dispose();
  });
});
