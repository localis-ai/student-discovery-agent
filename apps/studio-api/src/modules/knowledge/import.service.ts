import { ProductError } from '@/http/errors';
import { inKnowledgeTransaction, withKnowledgeClient, type Queryable } from '@/infrastructure/db/knowledge-client';
import { computeContentHash } from '@/shared/canonical';
import { knowledgeContentHash } from '@/modules/knowledge/content-hash';
import type { RequestContext } from '@/http/types';
import { kickIndexing } from '@/modules/knowledge/index-kick';
import { newId } from '@/modules/knowledge/ids';
import { ImportInputError, parseCsvRows, parseFiles, type ParsedRow } from '@/modules/knowledge/import';
import {
  documentContentSchema, type DocumentContent, type ImportCommitInput, type ImportPreviewInput,
} from '@/modules/knowledge/knowledge.schemas';
import {
  findImport, findLatestContent, insertImport, listFieldRows, type FieldRow,
} from '@/modules/knowledge/knowledge.repository';
import { requireKnowledgeBase } from '@/modules/knowledge/knowledge.service';
import { MetadataValidationError, namedMetadata, validateMetadata } from '@/modules/knowledge/metadata';
import { availableDocumentId, putDocument } from '@/modules/knowledge/writer';

export interface PreviewRowDTO {
  row: number;
  source: string;
  document_id: string | null;
  action: 'create' | 'update' | 'unchanged' | 'invalid';
  expected_revision: number | null;
  errors: string[];
  notes: string[];
  payload: DocumentContent | null;
}

type Outcome = 'created' | 'updated' | 'unchanged' | 'conflict' | 'failed';

export interface ImportReportDTO {
  import_id: string;
  created: number;
  updated: number;
  unchanged: number;
  conflict: number;
  failed: number;
  rows: Array<{ row: number; document_id: string; outcome: Outcome; revision: number | null; error: string | null }>;
}

function inputError(error: ImportInputError): ProductError {
  return new ProductError(422, 'VAL_INVALID_INPUT', error.message, false, {
    kind: 'validation', issues: [{ path: 'import', code: 'invalid_import', message: error.message, rule_id: null }],
  });
}

async function resolveRow(
  client: Queryable, kbId: string, fields: FieldRow[], parsed: ParsedRow, seen: Map<string, string>,
): Promise<PreviewRowDTO> {
  const invalid = (errors: string[]): PreviewRowDTO => ({
    row: parsed.row, source: parsed.source, document_id: parsed.documentId, action: 'invalid',
    expected_revision: null, errors, notes: [], payload: null,
  });
  if (parsed.errors.length > 0) return invalid(parsed.errors);
  const originalId = parsed.documentId!;
  const earlier = seen.get(originalId);
  if (earlier) return invalid([`Trùng document_id với ${earlier}`]);
  const documentId = await availableDocumentId(client, kbId, originalId, new Set(seen.keys()));
  seen.set(originalId, parsed.source);
  const notes: string[] = [];
  if (documentId !== originalId) {
    seen.set(documentId, parsed.source);
    notes.push(`ID đổi thành ${documentId} vì đã dùng ở knowledge base khác`);
  }

  const existing = await findLatestContent(client, documentId);
  const metadata = Object.fromEntries(Object.entries({
    ...(existing ? namedMetadata(fields, existing.metadata) : {}),
    ...parsed.metadata,
  }).filter(([, value]) => value !== null && value !== undefined));
  const candidate = {
    title: parsed.title ?? existing?.title,
    body: parsed.body ?? existing?.body,
    source_url: parsed.sourceUrl === undefined ? existing?.source_url ?? null : parsed.sourceUrl,
    metadata,
  };
  if (candidate.title === undefined || candidate.body === undefined) return invalid(['Document mới cần cả title và body']);
  const checked = documentContentSchema.safeParse(candidate);
  if (!checked.success) return invalid(checked.error.issues.map(issue => `${issue.path.join('.') || 'payload'}: ${issue.message}`));
  let stored: Record<string, unknown>;
  try {
    stored = validateMetadata(fields, checked.data.metadata);
  } catch (error) {
    if (error instanceof MetadataValidationError) return invalid(error.issues.map(issue => `${issue.field}: ${issue.message}`));
    throw error;
  }
  const hash = knowledgeContentHash(checked.data.title, checked.data.body, checked.data.source_url, stored);
  return {
    row: parsed.row, source: parsed.source, document_id: documentId,
    action: !existing ? 'create' : existing.content_hash === hash ? 'unchanged' : 'update',
    expected_revision: existing?.revision ?? 0, errors: [], notes, payload: checked.data,
  };
}

export async function previewImport(kbId: string, input: ImportPreviewInput): Promise<{ rows: PreviewRowDTO[] }> {
  return withKnowledgeClient(async client => {
    await requireKnowledgeBase(client, kbId);
    const fields = await listFieldRows(client, kbId);
    let parsed: ParsedRow[];
    try {
      parsed = input.kind === 'files' ? parseFiles(input.files) : parseCsvRows(input.content, input.mapping, fields);
    } catch (error) {
      throw error instanceof ImportInputError ? inputError(error) : error;
    }
    const seen = new Map<string, string>();
    const rows: PreviewRowDTO[] = [];
    for (const row of parsed) rows.push(await resolveRow(client, kbId, fields, row, seen));
    return { rows };
  });
}

function replay(stored: { request_hash: string; report: unknown }, requestHash: string): ImportReportDTO {
  if (stored.request_hash !== requestHash) {
    throw new ProductError(409, 'CONFLICT_IDEMPOTENCY_KEY', 'Idempotency key was used for a different import', false, {
      kind: 'idempotency_conflict',
    });
  }
  return stored.report as ImportReportDTO;
}

type ReportRow = ImportReportDTO['rows'][number];

async function commitRow(client: Queryable, kbId: string, item: ImportCommitInput['rows'][number]): Promise<ReportRow> {
  const row = (outcome: Outcome, revision: number | null, error: string | null): ReportRow =>
    ({ row: item.row, document_id: item.document_id, outcome, revision, error });
  await client.query('SAVEPOINT import_row');
  try {
    const result = await putDocument(client, kbId, item.document_id, item.payload, item.expected_revision);
    await client.query('RELEASE SAVEPOINT import_row');
    if (result.status === 'written') return row(result.outcome, result.revision, null);
    if (result.status === 'conflict') {
      return row('conflict', null, `Đã bị sửa sau lúc xem trước (revision ${result.actual}, xem trước ${item.expected_revision})`);
    }
    return row('failed', null, result.status === 'wrong_kb' ? 'document_id đã thuộc knowledge base khác' : 'Document không còn tồn tại');
  } catch (error) {
    if (!(error instanceof MetadataValidationError)) throw error;
    await client.query('ROLLBACK TO SAVEPOINT import_row');
    return row('failed', null, error.issues.map(issue => `${issue.field}: ${issue.message}`).join('; '));
  }
}

/**
 * One transaction for the whole import, holding an advisory lock on (kb, key) from the key lookup to the stored
 * report: a second request with the same key waits, then replays the report or answers 409 without writing anything.
 * A bad row rolls back to its savepoint only; any other error rolls back every row, so a retry starts clean.
 * Rows are written in document_id order so two imports touching the same documents lock them in the same order.
 */
export async function commitImport(kbId: string, input: ImportCommitInput, actor: string, ctx: RequestContext): Promise<ImportReportDTO> {
  const requestHash = computeContentHash(input.rows);
  const { report, fresh } = await inKnowledgeTransaction(async client => {
    await client.query('SELECT pg_advisory_xact_lock(hashtextextended($1, 0))', [`knowledge-import:${kbId}:${input.idempotency_key}`]);
    await requireKnowledgeBase(client, kbId);
    const stored = await findImport(client, kbId, input.idempotency_key);
    if (stored) return { report: replay(stored, requestHash), fresh: false };

    const rows: ReportRow[] = new Array(input.rows.length);
    const order = input.rows.map((_, index) => index)
      .sort((a, b) => input.rows[a]!.document_id.localeCompare(input.rows[b]!.document_id, 'en') || a - b);
    for (const index of order) rows[index] = await commitRow(client, kbId, input.rows[index]!);

    const built: ImportReportDTO = { import_id: newId('imp'), created: 0, updated: 0, unchanged: 0, conflict: 0, failed: 0, rows };
    for (const row of rows) built[row.outcome] += 1;
    if (!await insertImport(client, {
      id: built.import_id, kbId, key: input.idempotency_key, requestHash, report: built, createdBy: actor,
    })) throw new Error('knowledge import report already stored while holding its key lock');
    return { report: built, fresh: true };
  });
  if (fresh && report.created + report.updated > 0) kickIndexing(ctx);
  return report;
}
