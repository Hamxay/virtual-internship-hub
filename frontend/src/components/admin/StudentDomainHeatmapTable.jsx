import React from 'react';
import { readVelocityFromRow, scoreHeatmapCellClass } from '../../utils/commandCenterAnalytics';

/**
 * Pre-filtered rows and precomputed visible domain columns (smart sparse columns).
 * Rows may include chosen_domains (string[]) and chosen_domains_average from the admin analytics API.
 *
 * @param {{
 *   rows: object[],
 *   domainColumns: string[],
 * }} props
 */
export default function StudentDomainHeatmapTable({ rows = [], domainColumns = [] }) {
  const colCount = 5 + domainColumns.length;

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="min-w-full border-collapse text-left text-sm text-gray-900">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="sticky left-0 z-10 bg-gray-50 px-3 py-2.5 font-semibold text-gray-700">Student</th>
            <th className="min-w-[10rem] max-w-xs px-3 py-2.5 font-semibold text-gray-700">Target domains</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-semibold text-gray-700" title="Mean score in domains the student selected, among completed work only">
              Avg (targets)
            </th>
            {domainColumns.map((d) => (
              <th key={d} className="whitespace-nowrap px-3 py-2.5 font-semibold text-gray-700">
                {d}
              </th>
            ))}
            <th className="whitespace-nowrap px-3 py-2.5 font-semibold text-gray-700">Overall avg</th>
            <th className="whitespace-nowrap px-3 py-2.5 font-semibold text-gray-700">Progress Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={colCount} className="px-3 py-8 text-center text-gray-500">
                No rows to display.
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const chosen = Array.isArray(row.chosen_domains) ? row.chosen_domains : [];
              const chosenSet = new Set(chosen);
              return (
                <tr key={row.student_id ?? row.username} className="border-b border-gray-100 hover:bg-gray-50/80">
                  <td className="sticky left-0 z-10 bg-white px-3 py-2 font-medium text-gray-900 shadow-[1px_0_0_#e5e7eb]">
                    {row.username}
                  </td>
                  <td className="max-w-xs px-3 py-2 align-top text-xs text-gray-700" title={chosen.join(', ')}>
                    {chosen.length === 0 ? (
                      <span className="text-gray-400">—</span>
                    ) : (
                      <span className="line-clamp-2">{chosen.join(', ')}</span>
                    )}
                  </td>
                  <td
                    className={`whitespace-nowrap px-3 py-2 text-center ${
                      row.chosen_domains_average == null || !Number.isFinite(Number(row.chosen_domains_average))
                        ? 'bg-gray-50 text-gray-400'
                        : scoreHeatmapCellClass(row.chosen_domains_average)
                    }`}
                  >
                    {row.chosen_domains_average == null || !Number.isFinite(Number(row.chosen_domains_average))
                      ? '–'
                      : Number(row.chosen_domains_average).toFixed(2)}
                  </td>
                  {domainColumns.map((d) => {
                    const raw = row[d];
                    const isEmpty = raw == null || !Number.isFinite(Number(raw));
                    const isChosen = chosenSet.has(d);
                    const chosenMark = isChosen && !isEmpty ? ' ring-1 ring-inset ring-indigo-400/70' : '';
                    const chosenMarkEmpty = isChosen && isEmpty ? ' ring-1 ring-inset ring-indigo-200/80 bg-indigo-50/40' : '';
                    return (
                      <td
                        key={d}
                        className={`whitespace-nowrap px-3 py-2 text-center ${isEmpty ? 'bg-gray-50 text-gray-400' : scoreHeatmapCellClass(raw)}${chosenMark}${chosenMarkEmpty}`}
                        title={isChosen ? 'Student target domain' : undefined}
                      >
                        {isEmpty ? '–' : Number(raw).toFixed(2)}
                      </td>
                    );
                  })}
                  <td
                    className={`whitespace-nowrap px-3 py-2 text-center ${
                      row.overall_average == null || !Number.isFinite(Number(row.overall_average))
                        ? 'bg-gray-50 text-gray-400'
                        : scoreHeatmapCellClass(row.overall_average)
                    }`}
                  >
                    {row.overall_average == null || !Number.isFinite(Number(row.overall_average))
                      ? '–'
                      : Number(row.overall_average).toFixed(2)}
                  </td>
                  {(() => {
                    const velocity = readVelocityFromRow(row);
                    const velocityClass =
                      velocity == null
                        ? 'bg-gray-50 text-gray-400'
                        : velocity < 0
                          ? 'bg-red-50 text-red-600 font-medium'
                          : velocity > 0
                            ? 'bg-green-50 text-green-700 font-medium'
                            : 'bg-yellow-50 text-yellow-700 font-medium';
                    return (
                      <td className={`whitespace-nowrap px-3 py-2 text-center ${velocityClass}`}>
                        {velocity == null ? '–' : `${velocity >= 0 ? '+' : ''}${velocity.toFixed(1)}%`}
                      </td>
                    );
                  })()}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
