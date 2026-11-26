// `application/json` or a structured `application/*+json` type, optionally with parameters.
const JSON_MEDIA_TYPE = /^application\/(?:json|[a-z0-9!#$&^_.-]+\+json)$/;

export function isJsonContentType(header: string | null): boolean {
  if (!header) return false;
  const mediaType = header.split(';', 1)[0]!.trim().toLowerCase();
  return JSON_MEDIA_TYPE.test(mediaType);
}
