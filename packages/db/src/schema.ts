import { sqliteTable, text, integer, blob } from 'drizzle-orm/sqlite-core';

// Regular relational tables
export const documents = sqliteTable('documents', {
  id: text('id').primaryKey(),
  content: text('content').notNull(),
  metadata: text('metadata', { mode: 'json' }),
  createdAt: integer('created_at', { mode: 'timestamp' }).$defaultFn(() => new Date()),
});

// Note: sqlite-vec virtual tables are created manually in client.ts
// since Drizzle doesn't support virtual table definitions.
