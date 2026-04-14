import React from 'react';

function normalizeTags(tags) {
  if (!tags) return [];
  if (Array.isArray(tags)) return tags.filter(Boolean).map(String);
  return [];
}

function hasUrl(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

/**
 * @param {{ project: Record<string, unknown> }} props
 */
export default function PortfolioProjectCard({ project }) {
  const title = project?.template_title || 'Project';
  const description = project?.template_description || '';
  const tags = normalizeTags(project?.template_tags);
  const score = project?.overall_score;
  const scoreRounded = typeof score === 'number' && !Number.isNaN(score) ? Math.round(score) : null;
  const rawFeedback = project?.mentor_feedback;
  const mentorFeedback = typeof rawFeedback === 'string' ? rawFeedback.trim() : '';
  const repo = project?.repository_url;
  const artifact = project?.artifact_url;

  return (
    <article className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex flex-1 flex-col gap-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
          {description ? <p className="mt-2 text-sm leading-relaxed text-slate-600">{description}</p> : null}
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {scoreRounded !== null && (
          <div className="rounded-xl border border-amber-100 bg-amber-50/80 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-800/90">Score</p>
            <p className="mt-1 text-2xl font-bold text-amber-950">
              AI Score: <span className="tabular-nums">{scoreRounded}</span>
              <span className="text-lg font-semibold text-amber-900/80">/100</span>
            </p>
          </div>
        )}

        {mentorFeedback ? (
          <blockquote className="rounded-xl border-l-4 border-indigo-500 bg-indigo-50/60 px-4 py-3 text-sm leading-relaxed text-slate-800">
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Mentor verification</p>
            <p className="mt-2 text-slate-800">"{mentorFeedback}"</p>
          </blockquote>
        ) : null}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        {hasUrl(repo) && (
          <a
            href={repo.trim()}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex flex-1 min-w-[8rem] items-center justify-center rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            View code
          </a>
        )}
        {hasUrl(artifact) && (
          <a
            href={artifact.trim()}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex flex-1 min-w-[8rem] items-center justify-center rounded-lg border-2 border-indigo-600 bg-white px-4 py-2.5 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-50"
          >
            Live demo
          </a>
        )}
      </div>
    </article>
  );
}
