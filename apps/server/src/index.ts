import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { program } from 'commander';

const app = new Hono();

app.get('/', (c) => c.json({ status: 'ok' }));
app.get('/health', (c) => c.json({ healthy: true }));

// TODO: add routes for DB queries, AI endpoints, etc.

program
  .option('-p, --port <number>', 'port to listen on', '3001')
  .action((opts) => {
    const port = parseInt(opts.port);
    console.log(`Server starting on http://localhost:${port}`);
    serve({ fetch: app.fetch, port });
  });

program.parse();
