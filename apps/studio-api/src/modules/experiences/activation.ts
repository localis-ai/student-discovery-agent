import type { ProductDatabase } from '@/infrastructure/db/client';
import { ProductError } from '@/http/errors';
import { computeContentHash } from '@/modules/experiences/canonical';
import {
  findActiveRelease,
  findPointer,
  insertExperienceAudit,
  lockPointerKey,
  upsertPointer,
  type DeliveryEnvironment,
  type ExperienceActiveRow,
} from '@/modules/experiences/activation.repository';
import { findExperienceById, findReleaseById, type ExperienceReleaseRow } from '@/modules/experiences/experiences.repository';
import { toIsoZ, type ActivateReleaseInput, type RollbackInput } from '@/modules/experiences/experiences.schemas';
import { idempotent, type ServiceResult } from '@/modules/experiences/experiences.service';

export interface ActivePointerDTO {
  experience_id: string;
  environment: DeliveryEnvironment;
  revision: number;
  release_id: string | null;
  updated_at: string;
}

const toDTO = (row: ExperienceActiveRow): ActivePointerDTO => ({
  experience_id: row.experience_id, environment: row.environment, revision: row.revision,
  release_id: row.release_id, updated_at: toIsoZ(row.updated_at),
});

const notFound = (what: string) => new ProductError(404, 'RES_NOT_FOUND', `${what} not found`);

export async function readActivePointer(
  db: ProductDatabase, experienceId: string, environment: DeliveryEnvironment,
): Promise<ActivePointerDTO> {
  const experience = await findExperienceById(db, experienceId);
  if (!experience) throw notFound('Experience');
  const row = await findPointer(db, experienceId, environment);
  // No pointer yet: revision 0 is what the first activation must expect.
  return row ? toDTO(row) : {
    experience_id: experienceId, environment, revision: 0, release_id: null, updated_at: toIsoZ(experience.created_at),
  };
}

export async function activateRelease(
  db: ProductDatabase, releaseId: string, input: ActivateReleaseInput, actor: string,
): Promise<ServiceResult<ActivePointerDTO>> {
  const release = await findReleaseById(db, releaseId);
  if (!release) throw notFound('Experience release');
  return movePointer(db, release, input, actor, 'activate');
}

export async function rollbackRelease(
  db: ProductDatabase, experienceId: string, input: RollbackInput, actor: string,
): Promise<ServiceResult<ActivePointerDTO>> {
  const { target_release_id: targetId, ...move } = input;
  const release = await findReleaseById(db, targetId);
  if (!release || release.experience_id !== experienceId) throw notFound('Experience release');
  return movePointer(db, release, move, actor, 'rollback');
}

function checkPolicy(release: ExperienceReleaseRow, environment: DeliveryEnvironment): void {
  if (environment !== 'prod') return;
  const reject = (kind: string, message: string) =>
    new ProductError(422, 'VAL_INCOMPATIBLE_RELEASE', message, false, { kind, release_id: release.id, environment });
  if (release.is_demo) throw reject('demo_in_production', 'A demo release cannot be active in prod');
  if (release.approval_refs.length === 0) throw reject('approval_required', 'A prod release needs approval_refs');
}

async function movePointer(
  db: ProductDatabase, release: ExperienceReleaseRow, input: ActivateReleaseInput, actor: string,
  action: 'activate' | 'rollback',
): Promise<ServiceResult<ActivePointerDTO>> {
  checkPolicy(release, input.environment);
  const { idempotency_key: key, ...rest } = input;
  const payloadHash = computeContentHash({ ...rest, release_id: release.id, action });
  return idempotent(db, `experience-active:${release.experience_id}`, key, payloadHash, 200, async tx => {
    await lockPointerKey(tx, release.experience_id, input.environment);
    const current = await findPointer(tx, release.experience_id, input.environment);
    const revision = current?.revision ?? 0;
    const activeId = current?.release_id ?? null;
    // Both guards: the release id alone repeats after A -> B -> A, the monotonic revision never does.
    if (revision !== input.expected_revision || activeId !== input.expected_active_release_id) {
      throw new ProductError(409, 'CONFLICT_ACTIVE_RELEASE', 'The active release changed', false,
        { kind: 'stale_pointer', revision, release_id: activeId });
    }
    if (activeId === release.id) {
      throw new ProductError(409, 'CONFLICT_ACTIVE_RELEASE', 'Release is already active', false,
        { kind: 'no_changes', revision, release_id: activeId });
    }
    const moved = await upsertPointer(tx, {
      experience_id: release.experience_id, environment: input.environment, release_id: release.id,
      revision: revision + 1, updated_by: actor,
    });
    await insertExperienceAudit(tx, {
      actor, action: `experience.release.${action}`, target_id: release.experience_id, before_ref: activeId,
      after_ref: release.id, details: { environment: input.environment, reason: input.reason, revision: moved.revision },
    });
    return toDTO(moved);
  });
}

/** The active release as the runtime consumes it; `algorithm_profile` is the runtime's own mapping. */
export async function activeExperienceDescriptor(db: ProductDatabase, experienceId: string, environment: string) {
  const row = await findActiveRelease(db, experienceId, environment);
  if (!row) throw new ProductError(422, 'RES_EXPERIENCE_NOT_CONFIGURED', 'No active release for this experience');
  const { release } = row;
  return {
    environment, kind: 'experience' as const, release_id: release.id, content_hash: release.definition_hash,
    delivery_schema_version: 'experience.snapshot.v1' as const, content: release.content, is_demo: release.is_demo,
    definition_schema_version: release.definition_schema_version, engine_version: release.engine_version,
  };
}
