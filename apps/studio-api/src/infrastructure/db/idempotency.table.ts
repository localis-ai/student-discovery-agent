import { integer, jsonb, primaryKey, text, timestamp } from 'drizzle-orm/pg-core';
import { productSchema } from '@/infrastructure/db/product-schema';

/**
 * `product.idempotency_records` - Scoped idempotency records ensuring safe request replays.
 */
export const idempotencyRecords = productSchema.table(
  'idempotency_records',
  {
    scope: text('scope').notNull(),
    key: text('key').notNull(),
    request_hash: text('request_hash').notNull(),
    response_status: integer('response_status').notNull(),
    response_body: jsonb('response_body').$type<Record<string, unknown>>().notNull(),
    created_at: timestamp('created_at', { withTimezone: true, mode: 'date' }).defaultNow().notNull(),
  },
  (table) => [
    primaryKey({ columns: [table.scope, table.key] }),
  ],
);
