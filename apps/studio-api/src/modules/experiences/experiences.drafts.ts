import { randomBytes } from 'node:crypto';
import type { ProductDatabase, ProductExecutor } from '@/infrastructure/db/client';
import { idempotent, type IdempotentOptions, type IdempotentResult } from '@/infrastructure/db/idempotency';
import { ProductError } from '@/http/errors';
import { computeContentHash } from '@/shared/canonical';
import {
  findDraftByExperienceId,
  findExperienceWithDraft,
  insertExperienceWithDraft,
  listExperiences as repoListExperiences,
  patchExperienceMetadata,
  updateDraftContent,
} from '@/modules/experiences/experiences.repository';
import {
  toExperienceDraftDTO,
  toExperienceMetadataDTO,
  type CreateExperienceInput,
  type ExperienceDraftDTO,
  type ExperienceMetadataDTO,
  type PaginationQuery,
  type PatchExperienceInput,
} from '@/modules/experiences/experiences.schemas';

/** Keep the persisted semantic fingerprint independent of public revision field names. */
export function revisionPayloadHashes(
  payload: Record<string, unknown>,
  wireField: 'expected_metadata_revision' | 'expected_draft_revision',
): readonly string[] {
  const { expected_revision, ...rest } = payload;
  return [
    computeContentHash(payload),
    // Accept records written during the explicit-field rollout, with identical semantic values only.
    computeContentHash({ ...rest, [wireField]: expected_revision }),
  ];
}

/** Adapt only DTO revision fields; historical payloads and counters remain the committed result. */
function replayResponse(scope: string, stored: Record<string, unknown>): Record<string, unknown> {
  const rename = (value: Record<string, unknown>, field: string) => {
    if (!Object.hasOwn(value, 'revision')) return value;
    const { revision, ...rest } = value;
    return { ...rest, [field]: Object.hasOwn(rest, field) ? rest[field] : revision };
  };
  if (scope === 'create_experience' || scope.startsWith('patch:')) {
    const metadata = rename(stored, 'metadata_revision');
    const ref = metadata.draft_ref;
    return ref && typeof ref === 'object' && !Array.isArray(ref)
      ? { ...metadata, draft_ref: rename(ref as Record<string, unknown>, 'draft_revision') }
      : metadata;
  }
  return scope.startsWith('draft:') ? rename(stored, 'draft_revision') : stored;
}

/** Replay each stored record in the DTO shape of its own scope, including records written before the rename. */
export const replayOptions = (scope: string): IdempotentOptions => ({
  adaptReplay: (stored) => replayResponse(scope, stored),
});

export async function createExperience(
  db: ProductDatabase,
  input: CreateExperienceInput,
  user: { sub: string },
): Promise<IdempotentResult<ExperienceMetadataDTO>> {
  const scope = 'create_experience';
  const payloadHash = computeContentHash({
    name: input.name,
    description: input.description,
    activity_type: input.activity_type,
  });

  return idempotent(db, scope, input.idempotency_key, payloadHash, 201, async (tx) => {
    const experienceId = `exp_${randomBytes(8).toString('hex')}`;
    const { experience, draft } = await insertExperienceWithDraft(tx, {
      id: experienceId,
      name: input.name,
      description: input.description,
      activity_type: input.activity_type,
      updated_by: user.sub,
      initialDraftContent: {},
    });

    return toExperienceMetadataDTO(experience, {
      draft_id: draft.draft_id,
      draft_revision: draft.revision,
      content_hash: draft.content_hash,
    });
  }, replayOptions(scope));
}

export async function getExperience(
  db: ProductDatabase,
  id: string,
): Promise<ExperienceMetadataDTO> {
  const result = await findExperienceWithDraft(db, id);
  if (!result) {
    throw new ProductError(404, 'RESOURCE_NOT_FOUND', 'Experience not found');
  }

  const draftRef = result.draft
    ? {
        draft_id: result.draft.draft_id,
        draft_revision: result.draft.revision,
        content_hash: result.draft.content_hash,
      }
    : null;

  return toExperienceMetadataDTO(result.experience, draftRef);
}

export async function listExperiences(
  db: ProductDatabase,
  query: PaginationQuery,
): Promise<{ items: ExperienceMetadataDTO[]; next_cursor: string | null }> {
  const { items, next_cursor } = await repoListExperiences(db, {
    limit: query.limit,
    cursor: query.cursor,
  });

  return {
    items: items.map((item) => toExperienceMetadataDTO(item.experience, item.draftRef ? { draft_id: item.draftRef.draft_id, draft_revision: item.draftRef.revision, content_hash: item.draftRef.content_hash } : null)),
    next_cursor,
  };
}

export async function patchExperience(
  db: ProductDatabase,
  id: string,
  input: PatchExperienceInput,
): Promise<IdempotentResult<ExperienceMetadataDTO>> {
  const scope = `patch:${id}`;
  const payloadHash = revisionPayloadHashes({
    expected_revision: input.expected_metadata_revision,
    name: input.name,
    description: input.description,
  }, 'expected_metadata_revision');

  return idempotent(db, scope, input.idempotency_key, payloadHash, 200, async (tx) => {
    const result = await patchExperienceMetadata(tx, id, input.expected_metadata_revision, {
      name: input.name,
      description: input.description,
    });

    if (result.status === 'not_found') {
      throw new ProductError(404, 'RESOURCE_NOT_FOUND', 'Experience not found');
    }

    if (result.status === 'conflict') {
      throw new ProductError(409, 'REVISION_CONFLICT', 'Experience revision conflict', false, {
        kind: 'revision_conflict',
        expected_metadata_revision: input.expected_metadata_revision,
        actual_metadata_revision: result.current.revision,
      });
    }

    return toExperienceMetadataDTO(result.experience, result.draftRef ? { draft_id: result.draftRef.draft_id, draft_revision: result.draftRef.revision, content_hash: result.draftRef.content_hash } : null);
  }, replayOptions(scope));
}

export async function readExperienceDraft(
  db: ProductDatabase,
  experienceId: string,
): Promise<ExperienceDraftDTO> {
  const draft = await findDraftByExperienceId(db, experienceId);
  if (!draft) {
    throw new ProductError(404, 'RESOURCE_NOT_FOUND', 'Experience draft not found');
  }

  return toExperienceDraftDTO(draft);
}

export async function saveExperienceDraft(
  db: ProductDatabase,
  experienceId: string,
  input: {
    expected_draft_revision: number;
    idempotency_key: string;
    content: Record<string, unknown>;
  },
  user: { sub: string },
): Promise<IdempotentResult<ExperienceDraftDTO>> {
  const scope = `draft:${experienceId}`;
  const newHash = computeContentHash(input.content);
  const payloadHash = revisionPayloadHashes({
    expected_revision: input.expected_draft_revision,
    content: input.content,
  }, 'expected_draft_revision');

  return idempotent(db, scope, input.idempotency_key, payloadHash, 200, async (tx) => {
    const result = await updateDraftContent(
      tx,
      experienceId,
      input.expected_draft_revision,
      input.content,
      newHash,
      user.sub,
    );

    if (result.status === 'not_found') {
      throw new ProductError(404, 'RESOURCE_NOT_FOUND', 'Experience or draft not found');
    }

    if (result.status === 'conflict') {
      throw new ProductError(409, 'REVISION_CONFLICT', 'Draft revision conflict', false, {
        kind: 'revision_conflict',
        expected_draft_revision: input.expected_draft_revision,
        actual_draft_revision: result.current.revision,
        current_content_hash: result.current.content_hash,
      });
    }

    return toExperienceDraftDTO(result.draft);
  }, replayOptions(scope));
}

/** The draft the caller looked at: 404 when gone, 409 when its revision or content moved on. */
export async function requireDraftSnapshot(
  db: ProductExecutor,
  experienceId: string,
  expectedRevision: number,
  contentHash: string,
) {
  const draft = await findDraftByExperienceId(db, experienceId);
  if (!draft) {
    throw new ProductError(404, 'RESOURCE_NOT_FOUND', 'Experience or draft not found');
  }

  if (draft.revision !== expectedRevision) {
    throw new ProductError(
      409,
      'REVISION_CONFLICT',
      'Draft revision does not match expected revision',
      false,
      {
        kind: 'revision_conflict',
        expected_draft_revision: expectedRevision,
        actual_draft_revision: draft.revision,
      },
    );
  }

  if (draft.content_hash !== contentHash) {
    throw new ProductError(
      409,
      'STALE_REPORT',
      'Provided content hash does not match current draft content hash',
      false,
      {
        expected_content_hash: contentHash,
        actual_content_hash: draft.content_hash,
      },
    );
  }

  return draft;
}
