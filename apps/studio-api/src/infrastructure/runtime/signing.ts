import { createHash } from 'node:crypto';
import { SignJWT } from 'jose';

/** HS256 key as canonical padded base64 of at least 32 bytes; anything else is "not configured". */
export function signingKey(value: string | undefined): Uint8Array | null {
  if (!value) return null;
  const key = Buffer.from(value, 'base64');
  return key.length >= 32 && key.toString('base64') === value ? new Uint8Array(key) : null;
}

/** Token contract of the runtime ServiceVerifier: no owner, one purpose, bound to method + target + body. */
export async function signServiceRequest(
  method: string, target: string, body: string, key: Uint8Array, kid: string, nowMs = Date.now(),
  purpose = 'knowledge.retrieval',
): Promise<string> {
  const issuedAt = Math.floor(nowMs / 1000);
  return new SignJWT({
    caller_type: 'studio_service',
    purpose,
    method,
    request_target: target,
    body_sha256: createHash('sha256').update(body, 'utf8').digest('hex'),
  })
    .setProtectedHeader({ alg: 'HS256', typ: 'sda-internal+jwt', kid })
    .setIssuer('sda-studio-api')
    .setAudience('sda-agent-runtime')
    .setIssuedAt(issuedAt)
    .setExpirationTime(issuedAt + 30)
    .sign(key);
}
