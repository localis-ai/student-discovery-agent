import { z } from 'zod';

/** Field schemas shared by every module's request bodies (resource ids, idempotency keys, content hashes, revisions). */
export const resourceIdRegex = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
export const resourceIdSchema = z
  .string()
  .min(1)
  .regex(resourceIdRegex, 'Identifier must match ^[A-Za-z0-9][A-Za-z0-9._-]*$');

export const contentHashRegex = /^sha256:[a-f0-9]{64}$/;
export const contentHashSchema = z
  .string()
  .regex(contentHashRegex, 'Content hash must be formatted as sha256:<64-hex-digest>');

export const revisionSchema = z.number().int().min(0).max(Number.MAX_SAFE_INTEGER);

export const idempotencyKeySchema = z
  .string()
  .min(1)
  .regex(resourceIdRegex, 'Idempotency key must match ^[A-Za-z0-9][A-Za-z0-9._-]*$');
