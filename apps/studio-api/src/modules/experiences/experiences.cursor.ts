import { ProductError } from '@/http/errors';
import { encodeCursor, decodeCursor } from '@/http/cursor';
import { resourceIdSchema } from '@/http/field-schemas';

export interface ExperienceCursor {
  created_at: string;
  id: string;
}

export interface ReleaseCursor {
  published_at: string;
  id: string;
}

// Cursor timestamps keep PostgreSQL's microsecond precision: a millisecond JS Date would make
// keyset pagination skip rows that share the boundary millisecond.
const CURSOR_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;

function isCursorTimestamp(value: unknown): value is string {
  return typeof value === 'string' && CURSOR_TIMESTAMP.test(value) && !Number.isNaN(Date.parse(value));
}

function isCursorId(value: unknown): value is string {
  return resourceIdSchema.safeParse(value).success;
}

export function encodeExperienceCursor(cursor: { created_at: Date | string; id: string }): string {
  const d = typeof cursor.created_at === 'string' ? cursor.created_at : cursor.created_at.toISOString();
  return encodeCursor('experiences:created_at:desc', { created_at: d, id: cursor.id });
}

export function decodeExperienceCursor(cursorStr: string): ExperienceCursor {
  try {
    const parsed = decodeCursor(cursorStr, 'experiences:created_at:desc') as ExperienceCursor;
    if (!parsed || !isCursorTimestamp(parsed.created_at) || !isCursorId(parsed.id)) {
      throw new Error('Malformed cursor');
    }
    return { created_at: parsed.created_at, id: parsed.id };
  } catch {
    throw new ProductError(400, 'VAL_INVALID_REQUEST', 'Invalid pagination cursor');
  }
}

export function encodeReleaseCursor(cursor: { published_at: Date | string; id: string }, experienceId = ''): string {
  const d = typeof cursor.published_at === 'string' ? cursor.published_at : cursor.published_at.toISOString();
  return encodeCursor(`releases:${experienceId}:published_at:desc`, { published_at: d, id: cursor.id });
}

export function decodeReleaseCursor(cursorStr: string, experienceId = ''): ReleaseCursor {
  try {
    const parsed = decodeCursor(cursorStr, `releases:${experienceId}:published_at:desc`) as ReleaseCursor;
    if (!parsed || !isCursorTimestamp(parsed.published_at) || !isCursorId(parsed.id)) {
      throw new Error('Malformed cursor');
    }
    return { published_at: parsed.published_at, id: parsed.id };
  } catch {
    throw new ProductError(400, 'VAL_INVALID_REQUEST', 'Invalid pagination cursor');
  }
}
