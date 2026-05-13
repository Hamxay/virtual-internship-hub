import React from 'react';
import { mentorMediaAbsoluteUrl } from '../../utils/mentorMediaUrl';

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
  const uploaded = project?.uploaded_file;

  return (
    <article className="flex h-full flex-col rounded-xl border border-cyan-200 bg-white p-5 shadow-md shadow-cyan-200/50 sm:p-6">
      <div className="flex flex-1 flex-col gap-4">
        <div>
          <h2 className="text-lg font-semibold text-cyan-950 sm:text-xl">{title}</h2>
          {description ? (
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{description}</p>
          ) : null}
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded border border-cyan-200 bg-cyan-100 px-2 py-0.5 text-xs font-medium text-cyan-900"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {scoreRounded !== null && (
          <div className="rounded-r-md border-l-4 border-emerald-500 bg-emerald-100 py-3 pl-4 pr-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-emerald-800">Evaluation score</p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-emerald-950">
              {scoreRounded}
              <span className="text-base font-medium text-slate-500">/100</span>
            </p>
          </div>
        )}

        {mentorFeedback ? (
          <blockquote className="rounded-r-md border-l-4 border-sky-500 bg-sky-100 py-3 pl-4 pr-3 text-sm leading-relaxed text-slate-700">
            <p className="text-[11px] font-medium uppercase tracking-wide text-sky-800">Mentor review</p>
            <p className="mt-2">{mentorFeedback}</p>
          </blockquote>
        ) : null}
      </div>

      {hasUrl(uploaded) && (
        <div className="mt-5 border-t border-cyan-200 pt-5">
          <a
            href={mentorMediaAbsoluteUrl(uploaded.trim())}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center rounded-md border border-cyan-600 bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-700"
          >
            View submission file
          </a>
        </div>
      )}
    </article>
  );
}
