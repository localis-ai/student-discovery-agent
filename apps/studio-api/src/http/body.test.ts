import { describe, expect, it } from 'vitest';
import { isJsonContentType } from '@/http/body';
import { DEFAULT_MAX_BODY_BYTES, readStrictJsonBody } from '@/http/json-body';

function req(body: string | undefined, contentType?: string) {
  return new Request('http://x/api/v1/a', {
    method: 'POST',
    headers: contentType ? { 'content-type': contentType } : {},
    body,
  });
}

describe('isJsonContentType', () => {
  it.each(['application/json', 'application/json; charset=utf-8', 'Application/JSON;charset=UTF-8', 'application/merge-patch+json'])(
    'accepts %s',
    (ct) => expect(isJsonContentType(ct)).toBe(true),
  );

  it.each([null, 'text/plain', 'application/x-www-form-urlencoded', 'multipart/form-data; boundary=x', 'application/jsonx', 'text/json'])(
    'rejects %s',
    (ct) => expect(isJsonContentType(ct)).toBe(false),
  );
});

describe('readStrictJsonBody content type (CSRF hardening)', () => {
  it.each(['application/json', 'application/json; charset=utf-8', 'Application/JSON;charset=UTF-8', 'application/merge-patch+json'])(
    'accepts %s',
    async (ct) => {
      await expect(readStrictJsonBody(req('{"a":1}', ct))).resolves.toEqual({ a: 1 });
    },
  );

  it.each([undefined, 'text/plain', 'text/plain;charset=UTF-8', 'application/x-www-form-urlencoded', 'multipart/form-data; boundary=x', 'application/jsonx', 'text/json'])(
    'rejects %s with 415 VAL_UNSUPPORTED_MEDIA_TYPE',
    async (ct) => {
      await expect(readStrictJsonBody(req('{"a":1}', ct))).rejects.toMatchObject({ status: 415, code: 'VAL_UNSUPPORTED_MEDIA_TYPE' });
    },
  );

  it('optional empty body needs no content type; non-empty optional body still must be JSON', async () => {
    await expect(readStrictJsonBody(req(undefined), { optional: true })).resolves.toBeUndefined();
    await expect(readStrictJsonBody(req('{"a":1}', 'text/plain'), { optional: true })).rejects.toMatchObject({ status: 415 });
  });

  it('required body: empty -> 400, malformed -> 400', async () => {
    await expect(readStrictJsonBody(req('', 'application/json'))).rejects.toMatchObject({ status: 400, code: 'VAL_INVALID_REQUEST' });
    await expect(readStrictJsonBody(req('{', 'application/json'))).rejects.toMatchObject({ status: 400, code: 'VAL_INVALID_REQUEST' });
  });
});

describe('readStrictJsonBody on unauthenticated routes (login/register/refresh)', () => {
  it('rejects an oversize body with 413 VAL_PAYLOAD_TOO_LARGE before parsing', async () => {
    const big = `{"pad":"${'x'.repeat(DEFAULT_MAX_BODY_BYTES)}"}`;
    await expect(readStrictJsonBody(req(big, 'application/json'))).rejects.toMatchObject({
      status: 413,
      code: 'VAL_PAYLOAD_TOO_LARGE',
    });
  });

  it('rejects duplicate keys with 400 VAL_INVALID_REQUEST', async () => {
    await expect(readStrictJsonBody(req('{"email":"a@x.io","email":"b@x.io"}', 'application/json'))).rejects.toMatchObject({
      status: 400,
      code: 'VAL_INVALID_REQUEST',
    });
  });
});
