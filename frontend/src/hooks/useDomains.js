import { useState, useEffect } from 'react';
import { getDomains } from '../api/domains.api';

const CACHE_MS = 5 * 60 * 1000; // 5 minutes
let cachedList = null;
let cacheTime = 0;

/** Invalidate domains cache so next useDomains() refetches (e.g. after admin adds/edits/deletes a domain). */
export function invalidateDomainsCache() {
  cachedList = null;
  cacheTime = 0;
}

/**
 * Hook: fetch domains list (for signup dropdowns). Caches result to avoid refetch when toggling login/signup.
 * Returns { domains, loading, error }.
 */
export function useDomains(enabled = true) {
  const [domains, setDomains] = useState(() => (cachedList && enabled ? cachedList : []));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled) return;
    if (cachedList && Date.now() - cacheTime < CACHE_MS) {
      setDomains(cachedList);
      return;
    }
    setLoading(true);
    setError(null);
    getDomains()
      .then((list) => {
        cachedList = list;
        cacheTime = Date.now();
        setDomains(list);
      })
      .catch((err) => {
        setError(err);
        setDomains([]);
      })
      .finally(() => setLoading(false));
  }, [enabled]);

  return { domains, loading, error };
}
