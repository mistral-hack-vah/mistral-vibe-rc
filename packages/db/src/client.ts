import Database from 'better-sqlite3';
import * as sqliteVec from 'sqlite-vec';
import { drizzle } from 'drizzle-orm/better-sqlite3';
import * as schema from './schema.js';

const EMBEDDING_DIM = 1536; // adjust to your model's output

export function createDb(dbPath = 'data.db') {
  const sqlite = new Database(dbPath);
  sqlite.pragma('journal_mode = WAL');

  // Load sqlite-vec extension
  sqliteVec.load(sqlite);

  // Create the vector virtual table
  sqlite.exec(`
    CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
      id TEXT PRIMARY KEY,
      embedding float[${EMBEDDING_DIM}]
    );
  `);

  const db = drizzle(sqlite, { schema });

  return { db, sqlite };
}

export function insertEmbedding(
  sqlite: Database.Database,
  id: string,
  embedding: number[]
) {
  const stmt = sqlite.prepare(
    'INSERT OR REPLACE INTO vec_embeddings(id, embedding) VALUES (?, ?)'
  );
  stmt.run(id, JSON.stringify(embedding));
}

export function searchEmbeddings(
  sqlite: Database.Database,
  queryEmbedding: number[],
  limit = 10
): Array<{ id: string; distance: number }> {
  const stmt = sqlite.prepare(`
    SELECT id, distance
    FROM vec_embeddings
    WHERE embedding MATCH ?
    ORDER BY distance
    LIMIT ?
  `);
  return stmt.all(JSON.stringify(queryEmbedding), limit) as Array<{
    id: string;
    distance: number;
  }>;
}
