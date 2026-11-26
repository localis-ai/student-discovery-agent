import { vi } from 'vitest';
import type { ProductDatabase } from '@/infrastructure/db/client';
import type { IdempotencyRecordRow } from '@/infrastructure/db/idempotency';

/**
 * In-memory stand-in for the drizzle calls idempotency makes. Unit tests pass it as `db` so the real
 * lock, replay and save path runs. `stored` is the record every lookup finds; `inserted` collects saved records.
 */
export function fakeIdempotencyDb(stored?: Partial<IdempotencyRecordRow>) {
  const inserted: Record<string, unknown>[] = [];
  const db = {
    execute: vi.fn(async () => []),
    select: () => ({ from: () => ({ where: () => ({ limit: async () => (stored ? [stored] : []) }) }) }),
    insert: () => ({ values: async (row: Record<string, unknown>) => { inserted.push(row); } }),
    transaction: vi.fn(async (work: (tx: unknown) => unknown) => work(db)),
  };
  return { db: db as unknown as ProductDatabase, inserted };
}
