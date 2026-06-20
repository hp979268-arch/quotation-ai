import BASE from '../api';

const ABSOLUTE_PROTOCOL = /^(https?:|data:|blob:)/i;
const STATIC_IMAGE_PATH = /\/static\/images\//i;
const CACHE_BUSTER = 'v=20260620_live';

export function isAbsoluteUrl(value) {
  return ABSOLUTE_PROTOCOL.test(String(value || '').trim());
}

export function resolveAssetUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) {
    return '';
  }
  if (isAbsoluteUrl(raw)) {
    return raw;
  }
  if (raw.startsWith('//')) {
    return `https:${raw}`;
  }

  const normalizedBase = String(BASE || '').trim().replace(/\/+$/, '');
  if (!normalizedBase) {
    return raw;
  }

  if (raw.startsWith('/')) {
    const resolved = `${normalizedBase}${raw}`;
    return STATIC_IMAGE_PATH.test(raw) ? `${resolved}${resolved.includes('?') ? '&' : '?'}${CACHE_BUSTER}` : resolved;
  }

  const resolved = `${normalizedBase}/${raw}`;
  return STATIC_IMAGE_PATH.test(raw) ? `${resolved}${resolved.includes('?') ? '&' : '?'}${CACHE_BUSTER}` : resolved;
}
