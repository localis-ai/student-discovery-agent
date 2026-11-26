import { and, eq, sql } from 'drizzle-orm';
import type { ProductDatabase, ProductExecutor } from '@/infrastructure/db/client';
import { idempotencyRecords } from '@/infrastructure/db/schema';
import { ProductError } from '@/http/errors';

export type IdempotencyRecordRow = typeof idempotencyRecords.$inferSelect;

export interface IdempotentResult<T> {
  status: number;
  data: T;
  replayed?: boolean;
}

export interface IdempotentOptions {
  /** Maps a stored body to the current response shape, for records written by older code. */
  adaptReplay?: (stored: Record<string, unknown>) => Record<string, unknown>;
}

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

/**
 * Replay the stored response when the key was used with one of `payloadHash`; 409 when it was used with any
 * other payload. Callers may run it unlocked before slow work (runtime calls); `idempotent` runs it under the lock.
 */
export async function replayRecorded<T>(
  db: ProductExecutor,
  scope: string,
  key: string,
  payloadHash: string | readonly string[],
  options: IdempotentOptions = {},
): Promise<IdempotentResult<T> | undefined> {
  const existing = await findIdempotencyRecord(db, scope, key);
  if (!existing) return undefined;

  const hashes = typeof payloadHash === 'string' ? [payloadHash] : payloadHash;
  if (!hashes.includes(existing.request_hash)) {
    throw new ProductError(409, 'CONFLICT_IDEMPOTENCY_KEY', 'Idempotency key reused with different request payload');
  }

  const body = options.adaptReplay ? options.adaptReplay(existing.response_body) : existing.response_body;
  return { status: existing.response_status, data: body as T, replayed: true };
}

/**
 * One transaction per idempotent write: lock (scope, key), replay or reject a reused key, run the
 * business write, then store the response. A crash or error anywhere rolls back both the write and
 * the record, so a retry with the same key and payload re-executes instead of duplicating.
 */
export async function idempotent<T>(
  db: ProductDatabase,
  scope: string,
  key: string,
  payloadHash: string | readonly string[],
  status: number,
  work: (tx: ProductExecutor) => Promise<T>,
  options: IdempotentOptions = {},
): Promise<IdempotentResult<T>> {
  const hashes = typeof payloadHash === 'string' ? [payloadHash] : payloadHash;
  return withIdempotencyLock(db, scope, key, async (tx) => {
    const replayed = await replayRecorded<T>(tx, scope, key, hashes, options);
    if (replayed) return replayed;
    const data = await work(tx);
    await saveIdempotencyRecord(tx, {
      scope,
      key,
      request_hash: hashes[0]!,
      response_status: status,
      response_body: data as unknown as Record<string, unknown>,
    });
    return { status, data };
  });
}
