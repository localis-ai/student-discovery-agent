import { randomUUID } from 'node:crypto';
import { and, eq, sql } from 'drizzle-orm';
import { auditEvents, experienceActive, experienceReleases } from '@/infrastructure/db/schema';
import type { ExperienceReleaseRow, ProductExecutor } from '@/modules/experiences/experiences.repository';

export type DeliveryEnvironment = 'demo' | 'prod';
export type ExperienceActiveRow = typeof experienceActive.$inferSelect;

const pointerKey = (experienceId: string, environment: string) =>
  and(eq(experienceActive.experience_id, experienceId), eq(experienceActive.environment, environment as DeliveryEnvironment));

/**
 * Serialize pointer moves for one (experience, environment), including the very first one: a row lock cannot
 * guard a row that does not exist yet. Transaction-scoped, released on commit or rollback.
 */
export async function lockPointerKey(tx: ProductExecutor, experienceId: string, environment: string): Promise<void> {
  await tx.execute(sql`SELECT pg_advisory_xact_lock(hashtextextended(${`experience-active|${experienceId}|${environment}`}, 0))`);
}

export async function findPointer(
  db: ProductExecutor,
  experienceId: string,
  environment: string,
): Promise<ExperienceActiveRow | undefined> {
  const [row] = await db.select().from(experienceActive).where(pointerKey(experienceId, environment)).limit(1);
  return row;
}

export async function upsertPointer(
  tx: ProductExecutor,
  row: { experience_id: string; environment: DeliveryEnvironment; release_id: string; revision: number; updated_by: string },
): Promise<ExperienceActiveRow> {
  const [saved] = await tx
    .insert(experienceActive)
    .values(row)
    .onConflictDoUpdate({
      target: [experienceActive.experience_id, experienceActive.environment],
      set: { release_id: row.release_id, revision: row.revision, updated_by: row.updated_by, updated_at: sql`now()` },
    })
    .returning();
  if (!saved) throw new Error('upsert experience pointer returned no row');
  return saved;
}

export async function findActiveRelease(
  db: ProductExecutor,
  experienceId: string,
  environment: string,
): Promise<{ pointer: ExperienceActiveRow; release: ExperienceReleaseRow } | undefined> {
  const [row] = await db
    .select({ pointer: experienceActive, release: experienceReleases })
    .from(experienceActive)
    .innerJoin(experienceReleases, eq(experienceReleases.id, experienceActive.release_id))
    .where(pointerKey(experienceId, environment))
    .limit(1);
  return row;
}

/** One audit row per pointer move; never stores release content. */
export async function insertExperienceAudit(
  tx: ProductExecutor,
  event: { actor: string; action: string; target_id: string; before_ref: string | null; after_ref: string | null; details: Record<string, unknown> },
): Promise<void> {
  await tx.insert(auditEvents).values({
    id: randomUUID(), at: sql`clock_timestamp()`, target_kind: 'experience', outcome: 'success', ...event,
  });
}
