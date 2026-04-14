import React from 'react';

/**
 * @param {{ profile: { first_name?: string, last_name?: string, bio?: string | null, target_domains?: string[] } }} props
 */
export default function PortfolioHero({ profile }) {
  const first = profile?.first_name?.trim() || '';
  const last = profile?.last_name?.trim() || '';
  const fullName = [first, last].filter(Boolean).join(' ') || 'Student';
  const domains = Array.isArray(profile?.target_domains) ? profile.target_domains : [];
  const bio = profile?.bio?.trim();

  return (
    <header className="relative overflow-hidden rounded-2xl border border-slate-200/80 bg-gradient-to-br from-slate-50 via-white to-indigo-50/60 px-6 py-10 shadow-sm sm:px-10">
      <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-indigo-200/30 blur-3xl" aria-hidden />
      <div className="relative">
        <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Public portfolio</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">{fullName}</h1>
        {domains.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2">
            {domains.map((label) => (
              <span
                key={label}
                className="inline-flex items-center rounded-full border border-indigo-100 bg-white/90 px-3 py-1 text-sm font-medium text-indigo-800 shadow-sm"
              >
                {label}
              </span>
            ))}
          </div>
        )}
        {bio ? (
          <p className="mt-6 max-w-3xl text-base leading-relaxed text-slate-600">{bio}</p>
        ) : (
          <p className="mt-6 text-sm italic text-slate-400">No bio provided.</p>
        )}
      </div>
    </header>
  );
}
