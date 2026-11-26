import { randomBytes } from 'node:crypto';
import type { ProductDatabase } from '@/infrastructure/db/client';
import { idempotent, replayRecorded, type IdempotentResult } from '@/infrastructure/db/idempotency';
import { ProductError } from '@/http/errors';
import type { RequestContext } from '@/http/types';
import {
  findExperienceById,
  findReleaseById,
  insertExperienceRelease,
  listExperienceReleases as repoListReleases,
} from '@/modules/experiences/experiences.repository';
import { getPublishReportVerifier, type PublishReportVerifier } from '@/modules/experiences/experiences.reports';
import {
  experienceDefinitionStructuralSchema,
  toExperienceReleaseDTO,
  type ExperienceReleaseDTO,
  type PaginationQuery,
  type PublishReleaseInput,
} from '@/modules/experiences/experiences.schemas';
import {
  replayOptions,
  requireDraftSnapshot,
  revisionPayloadHashes,
} from '@/modules/experiences/experiences.drafts';

/**
 * Checks and the runtime report verification run before the transaction, so the (scope, key) advisory lock and the
 * connection are not held during a network call. The transaction then re-reads the draft: reports are immutable and
 * bound to the draft hash, so an unchanged draft means the verdict still stands.
 */
export async function publishExperienceRelease(
  db: ProductDatabase,
  experienceId: string,
  input: PublishReleaseInput,
  user: { sub: string },
  reports: PublishReportVerifier = getPublishReportVerifier(),
  ctx?: RequestContext,
): Promise<IdempotentResult<ExperienceReleaseDTO>> {
  const scope = `publish:${experienceId}`;
  const payloadHash = revisionPayloadHashes({
    expected_revision: input.expected_draft_revision,
    content_hash: input.content_hash,
    validation_id: input.validation_id,
    evaluation_id: input.evaluation_id,
    approval_refs: input.approval_refs,
  }, 'expected_draft_revision');

  const replayed = await replayRecorded<ExperienceReleaseDTO>(db, scope, input.idempotency_key, payloadHash, replayOptions(scope));
  if (replayed) return replayed;

  const draft = await requireDraftSnapshot(db, experienceId, input.expected_draft_revision, input.content_hash);

  const parseResult = experienceDefinitionStructuralSchema.safeParse(draft.content);
  if (!parseResult.success) {
    throw new ProductError(
      422,
      'PUBLISH_GATE_FAILED',
      'Draft content failed structural publish gate validation',
      false,
      {
        kind: 'validation',
        issues: parseResult.error.issues.map((i) => ({
          path: i.path.join('.'),
          code: i.code,
          message: i.message,
          rule_id: null,
        })),
      },
    );
  }

  const def = parseResult.data;
  const reportResult = await reports.verify(
    {
      experience_id: experienceId,
      definition_hash: draft.content_hash,
      definition_schema_version: def.schema_version,
      engine_version: def.engine_version,
      validation_id: input.validation_id,
      evaluation_id: input.evaluation_id,
    },
    db,
    ctx,
  );
  const verdict = typeof reportResult === 'boolean' ? { verified: reportResult } : reportResult;
  if (!verdict.verified) {
    // Fail closed: an unverifiable report must never become an immutable release.
    throw new ProductError(
      422,
      'PUBLISH_GATE_FAILED',
      verdict.reason ?? 'Validation and evaluation reports could not be verified',
      false,
      {
        kind: 'validation',
        issues: [
          {
            path: 'validation_id',
            code: 'report_unverified',
            message:
              verdict.reason ??
              'No passing validation/evaluation report is verifiable for this draft hash, schema and engine',
            rule_id: null,
          },
        ],
      },
    );
  }

  return idempotent(db, scope, input.idempotency_key, payloadHash, 201, async (tx) => {
    await requireDraftSnapshot(tx, experienceId, input.expected_draft_revision, input.content_hash);

    const releaseId = `exp_rel_${randomBytes(8).toString('hex')}`;

    const insertResult = await insertExperienceRelease(tx, {
      id: releaseId,
      experience_id: experienceId,
      definition_version: def.definition_version,
      definition_hash: draft.content_hash,
      definition_schema_version: def.schema_version,
      engine_version: def.engine_version,
      is_demo: def.is_demo,
      approval_refs: input.approval_refs,
      validation_id: input.validation_id,
      evaluation_id: input.evaluation_id,
      content: draft.content,
      published_by: user.sub,
    });

    if (insertResult.status === 'duplicate_version') {
      throw new ProductError(
        409,
        'REVISION_CONFLICT',
        `Definition version "${def.definition_version}" has already been published for this experience`,
      );
    }

    return toExperienceReleaseDTO(insertResult.release);
  }, replayOptions(scope));
}

export async function getExperienceRelease(
  db: ProductDatabase,
  releaseId: string,
): Promise<ExperienceReleaseDTO> {
  const release = await findReleaseById(db, releaseId);
  if (!release) {
    throw new ProductError(404, 'RESOURCE_NOT_FOUND', 'Release not found');
  }

  return toExperienceReleaseDTO(release);
}

export async function listExperienceReleases(
  db: ProductDatabase,
  experienceId: string,
  query: PaginationQuery,
): Promise<{ items: ExperienceReleaseDTO[]; next_cursor: string | null }> {
  const exp = await findExperienceById(db, experienceId);
  if (!exp) {
    throw new ProductError(404, 'RESOURCE_NOT_FOUND', 'Experience not found');
  }

  const { items, next_cursor } = await repoListReleases(db, experienceId, {
    limit: query.limit,
    cursor: query.cursor,
  });

  return {
    items: items.map(toExperienceReleaseDTO),
    next_cursor,
  };
}
