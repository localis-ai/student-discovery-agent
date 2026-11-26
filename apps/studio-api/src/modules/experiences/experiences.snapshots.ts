import type { ProductDatabase } from '@/infrastructure/db/client';
import { idempotent, replayRecorded, type IdempotentResult } from '@/infrastructure/db/idempotency';
import { ProductError } from '@/http/errors';
import type { RequestContext } from '@/http/types';
import { computeContentHash } from '@/shared/canonical';
import { insertExperienceReport } from '@/modules/experiences/experiences.repository';
import {
  getExperienceRuntimeClient,
  type EvaluationReport,
  type ExperienceSnapshotCommandInput,
  type ValidationReport,
} from '@/modules/experiences/runtime-client';
import type { SnapshotCommandInput } from '@/modules/experiences/experiences.schemas';
import { replayOptions, requireDraftSnapshot } from '@/modules/experiences/experiences.drafts';

/** A report must describe exactly the draft snapshot that was sent; never persist one for another snapshot. */
function assertReportMatchesRequest(
  report: { experience_id: string; content_hash: string; draft_revision: number },
  experienceId: string,
  input: { content_hash: string; expected_revision: number },
): void {
  if (
    report.experience_id !== experienceId ||
    report.content_hash !== input.content_hash ||
    report.draft_revision !== input.expected_revision
  ) {
    throw new ProductError(503, 'SYS_UNAVAILABLE', 'Runtime returned a report for a different draft snapshot', false, {
      kind: 'report_mismatch',
    });
  }
}

type SnapshotReport = ValidationReport | EvaluationReport;

/**
 * The runtime call runs before the transaction. Concurrent requests with one key both call it; the runtime answers
 * the same snapshot and key with the same report, and the idempotency lock then lets exactly one of them store it.
 */
async function runSnapshotCommand<R extends SnapshotReport>(
  db: ProductDatabase,
  experienceId: string,
  input: SnapshotCommandInput,
  ctx: RequestContext,
  command: {
    scope: string;
    kind: 'validation' | 'evaluation';
    run: (cmd: ExperienceSnapshotCommandInput, ctx: RequestContext) => Promise<R>;
  },
): Promise<IdempotentResult<R>> {
  const scope = `${command.scope}:${experienceId}`;
  const payloadHash = computeContentHash({
    expected_revision: input.expected_revision,
    content_hash: input.content_hash,
  });

  const replayed = await replayRecorded<R>(db, scope, input.idempotency_key, [payloadHash], replayOptions(scope));
  if (replayed) return replayed;

  const draft = await requireDraftSnapshot(db, experienceId, input.expected_revision, input.content_hash);
  const report = await command.run(
    {
      experience_id: experienceId,
      definition: draft.content,
      expected_revision: input.expected_revision,
      content_hash: input.content_hash,
      idempotency_key: input.idempotency_key,
    },
    ctx,
  );
  assertReportMatchesRequest(report, experienceId, input);

  return idempotent(db, scope, input.idempotency_key, payloadHash, 201, async (tx) => {
    // The report describes the draft that was sent; it must not be stored if the draft moved meanwhile.
    await requireDraftSnapshot(tx, experienceId, input.expected_revision, input.content_hash);
    await insertExperienceReport(tx, {
      id: report.id,
      experience_id: experienceId,
      kind: command.kind,
      draft_revision: report.draft_revision,
      content_hash: report.content_hash,
      definition_schema_version: report.definition_schema_version,
      engine_version: report.engine_version,
      status: report.status,
      mandatory_passed: report.mandatory_passed,
      report: report as unknown as Record<string, unknown>,
    });
    return report;
  }, replayOptions(scope));
}

export function validateExperienceDraft(
  db: ProductDatabase,
  experienceId: string,
  input: SnapshotCommandInput,
  ctx: RequestContext,
): Promise<IdempotentResult<ValidationReport>> {
  return runSnapshotCommand(db, experienceId, input, ctx, {
    scope: 'validate',
    kind: 'validation',
    run: (cmd, c) => getExperienceRuntimeClient().validate(cmd, c),
  });
}

export function evaluateExperienceDraft(
  db: ProductDatabase,
  experienceId: string,
  input: SnapshotCommandInput,
  ctx: RequestContext,
): Promise<IdempotentResult<EvaluationReport>> {
  return runSnapshotCommand(db, experienceId, input, ctx, {
    scope: 'evaluate',
    kind: 'evaluation',
    run: (cmd, c) => getExperienceRuntimeClient().evaluate(cmd, c),
  });
}
