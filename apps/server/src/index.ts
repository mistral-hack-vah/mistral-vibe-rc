import { serve } from '@hono/node-server';
import { createNodeWebSocket } from '@hono/node-ws';
import { Hono } from 'hono';
import { program } from 'commander';

const app = new Hono();
const { injectWebSocket, upgradeWebSocket } = createNodeWebSocket({ app });

app.get('/', (c) => c.json({ status: 'ok' }));
app.get('/health', (c) => c.json({ healthy: true }));

// ─── WebSocket: control channel (JSON text frames) ───
app.get(
  '/ws/control',
  upgradeWebSocket(() => ({
    onOpen(_event, ws) {
      console.log('[ws/control] client connected');
    },
    onMessage(event, ws) {
      const data = typeof event.data === 'string' ? event.data : '<binary>';
      console.log('[ws/control] ←', data);
      // Echo back for now
      ws.send(event.data);
    },
    onClose() {
      console.log('[ws/control] client disconnected');
    },
  })),
);

// ─── WebSocket: audio channel (binary PCM frames + JSON control) ───
app.get(
  '/ws/audio',
  upgradeWebSocket(() => {
    let chunkIndex = 0;
    let totalBytes = 0;
    let streaming = false;

    return {
      onOpen(_event, ws) {
        console.log('[ws/audio] client connected');
      },
      onMessage(event, ws) {
        if (typeof event.data === 'string') {
          const msg = JSON.parse(event.data);
          if (msg.type === 'audio_start') {
            streaming = true;
            chunkIndex = 0;
            totalBytes = 0;
            console.log(`[ws/audio] ← audio_start (rate=${msg.sampleRate} enc=${msg.encoding} ch=${msg.channels})`);
          } else if (msg.type === 'audio_end') {
            console.log(`[ws/audio] ← audio_end (${chunkIndex} chunks, ${totalBytes} bytes total)`);
            streaming = false;
          } else {
            console.log('[ws/audio] ←', event.data);
          }
        } else {
          const size = event.data instanceof ArrayBuffer
            ? event.data.byteLength
            : (event.data as Buffer).length;
          chunkIndex++;
          totalBytes += size;
          console.log(`[ws/audio] ← chunk #${chunkIndex} (${size} bytes, ${totalBytes} total)`);
        }
      },
      onClose() {
        if (streaming) {
          console.log(`[ws/audio] client disconnected mid-stream (${chunkIndex} chunks, ${totalBytes} bytes)`);
        } else {
          console.log('[ws/audio] client disconnected');
        }
      },
    };
  }),
);

// TODO: add routes for DB queries, AI endpoints, etc.

program
  .option('-p, --port <number>', 'port to listen on', '14096')
  .action((opts) => {
    const port = parseInt(opts.port);
    console.log(`Server starting on http://localhost:${port}`);
    const server = serve({ fetch: app.fetch, port });
    injectWebSocket(server);
  });

program.parse();
