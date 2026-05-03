import { API_BASE_URL } from '../api/client';

/** Resolve relative media paths to absolute URLs for downloads / links. */
export function mentorMediaAbsoluteUrl(path) {
  if (!path) return '';
  const s = String(path);
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  const origin = API_BASE_URL.replace(/\/api\/?$/, '');
  return s.startsWith('/') ? `${origin}${s}` : `${origin}/${s}`;
}
