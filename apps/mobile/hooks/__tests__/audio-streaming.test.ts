import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { WebSocket } from 'ws';
import { MockWSServer } from './helpers/mock-ws-server';
import { ReconnectingSocket } from '../reconnecting-socket';

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

describe('Audio streaming', () => {
  let server: MockWSServer;

  beforeEach(async () => {
    server = new MockWSServer();
    await server.start();
  });

  afterEach(async () => {
    await server.close();
  });

  it('sends audio_start, binary PCM chunks, and audio_end', async () => {
    const sock = new ReconnectingSocket({ url: server.url });
    await waitFor(() => sock.status === 'connected');

    // Send audio_start JSON frame
    const audioStart = JSON.stringify({
      type: 'audio_start',
      sampleRate: 44100,
      encoding: 'pcm_16bit',
      channels: 1,
    });
    sock.send(audioStart);

    // Simulate sending PCM chunks as binary frames
    const chunk1 = new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7]).buffer;
    const chunk2 = new Uint8Array([8, 9, 10, 11, 12, 13, 14, 15]).buffer;
    sock.sendBinary(chunk1);
    sock.sendBinary(chunk2);

    // Send audio_end JSON frame
    const audioEnd = JSON.stringify({ type: 'audio_end' });
    sock.send(audioEnd);

    // Wait for all 4 messages
    await waitFor(() => server.received.length === 4);

    // Verify audio_start
    expect(typeof server.received[0]).toBe('string');
    const startMsg = JSON.parse(server.received[0] as string);
    expect(startMsg.type).toBe('audio_start');
    expect(startMsg.sampleRate).toBe(44100);
    expect(startMsg.encoding).toBe('pcm_16bit');
    expect(startMsg.channels).toBe(1);

    // Verify binary chunks
    expect(Buffer.isBuffer(server.received[1])).toBe(true);
    expect([...(server.received[1] as Buffer)]).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
    expect(Buffer.isBuffer(server.received[2])).toBe(true);
    expect([...(server.received[2] as Buffer)]).toEqual([8, 9, 10, 11, 12, 13, 14, 15]);

    // Verify audio_end
    expect(typeof server.received[3]).toBe('string');
    const endMsg = JSON.parse(server.received[3] as string);
    expect(endMsg.type).toBe('audio_end');

    sock.dispose();
  });

  it('handles rapid sequential binary chunks', async () => {
    const sock = new ReconnectingSocket({ url: server.url });
    await waitFor(() => sock.status === 'connected');

    const chunkCount = 50;
    for (let i = 0; i < chunkCount; i++) {
      const chunk = new Uint8Array(160); // 10ms of 16kHz 16-bit mono
      chunk[0] = i;
      sock.sendBinary(chunk.buffer);
    }

    await waitFor(() => server.received.length === chunkCount);
    expect(server.received.length).toBe(chunkCount);

    // Verify ordering by checking first byte of each chunk
    for (let i = 0; i < chunkCount; i++) {
      const buf = server.received[i] as Buffer;
      expect(buf[0]).toBe(i);
    }

    sock.dispose();
  });

  it('sendBinary throws when socket is not connected', () => {
    const sock = new ReconnectingSocket({
      url: server.url,
      lazy: true,
    });

    const chunk = new Uint8Array([1, 2, 3]).buffer;
    expect(() => sock.sendBinary(chunk)).toThrow('Socket is not connected');
    sock.dispose();
  });

  it('can interleave JSON and binary frames', async () => {
    const sock = new ReconnectingSocket({ url: server.url });
    await waitFor(() => sock.status === 'connected');

    sock.send(JSON.stringify({ type: 'audio_start', sampleRate: 16000, encoding: 'pcm_16bit', channels: 1 }));
    sock.sendBinary(new Uint8Array([10, 20]).buffer);
    sock.send(JSON.stringify({ type: 'metadata', seq: 1 }));
    sock.sendBinary(new Uint8Array([30, 40]).buffer);
    sock.send(JSON.stringify({ type: 'audio_end' }));

    await waitFor(() => server.received.length === 5);

    // Text frames
    expect(typeof server.received[0]).toBe('string');
    expect(typeof server.received[2]).toBe('string');
    expect(typeof server.received[4]).toBe('string');

    // Binary frames
    expect(Buffer.isBuffer(server.received[1])).toBe(true);
    expect(Buffer.isBuffer(server.received[3])).toBe(true);

    sock.dispose();
  });
});
