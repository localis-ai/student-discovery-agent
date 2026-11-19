import { randomBytes } from 'node:crypto';
import { z } from 'zod';
import type { ProductDatabase } from '@/infrastructure/db/client';
import { computeContentHash } from '@/shared/canonical';
import { findPointer, insertExperienceAudit, lockPointerKey, upsertPointer } from '@/modules/experiences/activation.repository';
import {
  findExperienceById,
  findReleaseByVersion,
  insertExperienceRelease,
  insertExperienceWithDraft,
} from '@/modules/experiences/experiences.repository';
import { resourceIdSchema } from '@/modules/experiences/experiences.schemas';

/**
 * Only the release metadata. The publish gate's structural schema accepts schema 1.0 alone, while the packaged
 * experiences are 2.0; the runtime validates the full definition when it resolves the release.
 */
export const seedDefinitionHeaderSchema = z.object({
  schema_version: z.enum(['1.0', '2.0']),
  definition_version: z.string().min(1),
  engine_version: z.string().min(1),
  is_demo: z.boolean(),
}).passthrough();

const SEED = 'seed';

/**
 * Bootstrap one experience from a packaged definition: experience + draft when missing, a release per new
 * definition_version, and the demo pointer only when none exists. Seed releases skip the validation/evaluation
 * gate on purpose: this content already runs in production from the runtime image. Idempotent.
 */
export async function seedExperience(
  db: ProductDatabase,
  experienceId: string,
  content: Record<string, unknown>,
): Promise<'seeded' | 'released' | 'skipped'> {
  resourceIdSchema.parse(experienceId);
  const header = seedDefinitionHeaderSchema.parse(content);
  const hash = computeContentHash(content);
  return db.transaction(async tx => {
    await lockPointerKey(tx, experienceId, 'demo');
    if (!(await findExperienceById(tx, experienceId))) {
      await insertExperienceWithDraft(tx, { id: experienceId, name: experienceId, updated_by: SEED, initialDraftContent: content });
    }
    let release = await findReleaseByVersion(tx, experienceId, header.definition_version);
    if (release && release.definition_hash !== hash) {
      throw new Error(`${experienceId}: definition_version ${header.definition_version} was already released with different content`);
    }
    let released = false;
    if (!release) {
      const inserted = await insertExperienceRelease(tx, {
        id: `exp_rel_${randomBytes(8).toString('hex')}`, experience_id: experienceId,
        definition_version: header.definition_version, definition_hash: hash,
        definition_schema_version: header.schema_version, engine_version: header.engine_version,
        is_demo: header.is_demo, approval_refs: [], validation_id: SEED, evaluation_id: SEED, content, published_by: SEED,
      });
      if (inserted.status !== 'ok') throw new Error(`${experienceId}: release insert failed (${inserted.status})`);
      release = inserted.release;
      released = true;
    }
    if (await findPointer(tx, experienceId, 'demo')) return released ? 'released' : 'skipped';
    const moved = await upsertPointer(tx, {
      experience_id: experienceId, environment: 'demo', release_id: release.id, revision: 1, updated_by: SEED,
    });
    await insertExperienceAudit(tx, {
      actor: SEED, action: 'experience.release.activate', target_id: experienceId, before_ref: null,
      after_ref: release.id, details: { environment: 'demo', reason: 'bootstrap', revision: moved.revision },
    });
    return 'seeded';
  });
}
