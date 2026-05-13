import React from 'react';

/**
 * @param {{ displayName: string, domains: string[], bio: string }} props
 */
export default function PortfolioHero({ displayName, domains, bio }) {
  return (
    <header className="rounded-xl border border-cyan-200 bg-gradient-to-r from-cyan-100 via-sky-50 to-teal-100 px-4 pb-8 pt-4 shadow-sm shadow-cyan-200/40 sm:px-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-800">Portfolio</p>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight text-cyan-950 sm:text-3xl">{displayName}</h1>
      {domains.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-2" aria-label="Focus areas">
          {domains.map((label) => (
            <li key={label}>
              <span className="inline-block rounded-md border border-cyan-200 bg-white/95 px-2.5 py-1 text-sm font-semibold text-cyan-900 shadow-sm shadow-cyan-200/40">
                {label}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-6 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-[15px]">{bio}</p>
    </header>
  );
}
