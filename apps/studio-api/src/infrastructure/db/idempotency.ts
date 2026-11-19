import { and, eq, sql } from 'drizzle-orm';
import type { ProductDatabase, ProductExecutor } from '@/infrastructure/db/client';
import { idempotencyRecords } from '@/infrastructure/db/schema';

export type IdempotencyRecordRow = typeof idempotencyRecords.$inferSelect;

export async function findIdempotencyRecord(
  db: ProductExecutor,
  scope: string,
  key: string,
): Promise<IdempotencyRecordRow | undefined> {
  const [row] = await db
    .select()
    .from(idempotencyRecords)
    .where(and(eq(idempotencyRecords.scope, scope), eq(idempotencyRecords.key, key)))
    .limit(1);
  return row;
}

export async function saveIdempotencyRecord(
  db: ProductExecutor,
  record: {
    scope: string;
    key: string;
    request_hash: string;
    response_status: number;
    response_body: Record<string, unknown>;
  },
): Promise<void> {
  // No ON CONFLICT: callers hold the key's advisory lock, so a conflict here is a real fault, not a race.
  await db.insert(idempotencyRecords).values(record);
}

/**
 * Run `work` in one transaction that first takes a transaction-scoped advisory lock on (scope, key).
 * Requests reusing a key serialize here; under READ COMMITTED the next one then sees the committed
 * record and replays it. The record and the business write therefore commit or roll back together.
 */
export async function withIdempotencyLock<T>(
  db: ProductDatabase,
  scope: string,
  key: string,
  work: (tx: ProductExecutor) => Promise<T>,
): Promise<T> {
  return db.transaction(async (tx) => {
    await tx.execute(sql`SELECT pg_advisory_xact_lock(hashtextextended(${`${scope}|${key}`}, 0))`);
    return work(tx);
  });
}
