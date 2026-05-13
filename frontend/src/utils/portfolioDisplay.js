/**
 * Placeholders for public portfolio when the student has not completed their profile.
 * Real values from the API always take precedence.
 */

const DEFAULT_DISPLAY_FALLBACK = 'Professional learner';

const DEFAULT_BIO =
  'Focused on building practical skills through structured projects and mentor feedback on the Virtual Internship Hub. ' +
  'Update your profile to share a personal introduction with visitors.';

const DEFAULT_DOMAINS = ['Professional development', 'Project-based learning', 'Industry skills'];

/**
 * Derive a readable name from username (e.g. arham12 → Arham, dev_user → Dev User).
 * @param {string | undefined} username
 * @returns {string}
 */
export function displayNameFromUsername(username) {
  if (!username || typeof username !== 'string') return '';
  const base = username
    .trim()
    .replace(/@.+$/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\d+$/g, '')
    .trim();
  if (!base) return '';
  return base
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

/**
 * @param {Record<string, unknown>} profile - raw API profile
 * @param {string | undefined} username - route param
 * @returns {{ displayName: string, domains: string[], bio: string, slugBase: string }}
 */
export function resolvePortfolioDisplay(profile, username) {
  const first = typeof profile?.first_name === 'string' ? profile.first_name.trim() : '';
  const last = typeof profile?.last_name === 'string' ? profile.last_name.trim() : '';
  const fromOfficial = [first, last].filter(Boolean).join(' ');

  let displayName = fromOfficial;
  if (!displayName) {
    displayName = displayNameFromUsername(username) || DEFAULT_DISPLAY_FALLBACK;
  }

  const rawDomains = Array.isArray(profile?.target_domains)
    ? profile.target_domains.map((d) => (typeof d === 'string' ? d.trim() : String(d))).filter(Boolean)
    : [];
  const domains = rawDomains.length > 0 ? rawDomains : [...DEFAULT_DOMAINS];

  const rawBio = typeof profile?.bio === 'string' ? profile.bio.trim() : '';
  const bio = rawBio || DEFAULT_BIO;

  const slugBase = fromOfficial
    ? `${first}-${last}`.replace(/\s+/g, '-')
    : (displayNameFromUsername(username) || username || 'portfolio').replace(/\s+/g, '-');

  return { displayName, domains, bio, slugBase };
}
