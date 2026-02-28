export function greet(name: string): string {
  return `Hello from ${name}!`;
}

export interface EmbeddingRecord {
  id: string;
  content: string;
  embedding: number[];
  metadata?: Record<string, unknown>;
}
