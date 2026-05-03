import React from 'react';

function studentDisplayName(row) {
  const fn = (row.first_name || '').trim();
  const ln = (row.last_name || '').trim();
  const full = `${fn} ${ln}`.trim();
  return full || '—';
}

/**
 * @param {{ students: object[], loading: boolean }} props
 */
export default function StudentProgressTable({ students = [], loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-slate-200 bg-white py-16 text-slate-500">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600" aria-hidden />
        <span className="ml-3 text-sm font-medium">Loading students…</span>
      </div>
    );
  }

  if (!students.length) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/80 px-6 py-14 text-center text-sm text-slate-600">
        No students match your expertise domain yet, or your domain is not set.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th scope="col" className="px-5 py-3.5 font-semibold text-slate-700">
                Student name
              </th>
              <th scope="col" className="px-5 py-3.5 font-semibold text-slate-700">
                Projects completed
              </th>
              <th scope="col" className="px-5 py-3.5 font-semibold text-slate-700">
                Average score
              </th>
              <th scope="col" className="px-5 py-3.5 font-semibold text-slate-700">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {students.map((row, idx) => {
              const atRisk = Boolean(row.is_at_risk);
              const rowKey = `${studentDisplayName(row)}-${idx}`;
              return (
                <tr
                  key={rowKey}
                  className={
                    atRisk
                      ? 'border-l-4 border-l-red-500 bg-red-50/90'
                      : 'bg-white hover:bg-slate-50/80'
                  }
                >
                  <td className="px-5 py-4 font-medium text-slate-900">{studentDisplayName(row)}</td>
                  <td className="px-5 py-4 tabular-nums text-slate-700">
                    {row.projects_completed != null ? row.projects_completed : '—'}
                  </td>
                  <td className="px-5 py-4 tabular-nums text-slate-700">
                    {row.domain_average != null ? `${row.domain_average}` : '—'}
                  </td>
                  <td className="px-5 py-4">
                    {atRisk ? (
                      <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800 ring-1 ring-inset ring-red-200">
                        Needs help
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-200">
                        On track
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
