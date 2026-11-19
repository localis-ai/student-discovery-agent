import { createHash } from 'node:crypto';
import { decodeProtectedHeader, jwtVerify } from 'jose';
import { describe, expect, it } from 'vitest';
import { signingKey, signServiceRequest } from '@/infrastructure/runtime/signing';

const KEY = new TextEncoder().encode('studio-test-key-at-least-32-bytes!!');

describe('signServiceRequest', () => {
  it('binds the studio service token to method, target and body', async () => {
    const target = '/api/v1/internal/knowledge/retrieval';
    const body = '{"knowledge_id":"kb","query":"học phí"}';
    const token = await signServiceRequest('POST', target, body, KEY, 'studio', Date.UTC(2026, 9, 27));
    expect(decodeProtectedHeader(token)).toEqual({ alg: 'HS256', typ: 'sda-internal+jwt', kid: 'studio' });
    const { payload } = await jwtVerify(token, KEY, {
      issuer: 'sda-studio-api', audience: 'sda-agent-runtime', currentDate: new Date(Date.UTC(2026, 9, 27, 0, 0, 10)),
    });
    expect(payload).toMatchObject({
      caller_type: 'studio_service', purpose: 'knowledge.retrieval', method: 'POST', request_target: target,
      body_sha256: createHash('sha256').update(body, 'utf8').digest('hex'), aud: 'sda-agent-runtime',
    });
    expect(payload.exp! - payload.iat!).toBe(30);
    expect(payload).not.toHaveProperty('owner_id');
  });
});

describe('signingKey', () => {
  it('accepts canonical base64 of at least 32 bytes only', () => {
    const good = Buffer.alloc(32, 7).toString('base64');
    expect(signingKey(good)).toHaveLength(32);
    expect(signingKey(undefined)).toBeNull();
    expect(signingKey(Buffer.alloc(31, 7).toString('base64'))).toBeNull();
    expect(signingKey(`${good}\n`)).toBeNull();
  });
});
