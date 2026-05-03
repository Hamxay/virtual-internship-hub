import React from 'react';
import { scoreHeatmapCellClass } from '../../utils/commandCenterAnalytics';

/**
 * Pre-filtered rows and precomputed visible domain columns (smart sparse columns).
 *
 * @param {{
 *   rows: object[],
 *   domainColumns: string[],
 * }} props
 */
export default function StudentDomainHeatmapTable({ rows = [], domainColumns = [] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="min-w-full border-collapse text-left text-sm text-gray-900">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="sticky left-0 z-10 bg-gray-50 px-3 py-2.5 font-semibold text-gray-700">Student Name</th>
            {domainColumns.map((d) => (
              <th key={d} className="whitespace-nowrap px-3 py-2.5 font-semibold text-gray-700">
                {d}
              </th>
            ))}
            <th className="whitespace-nowrap px-3 py-2.5 font-semibold text-gray-700">Overall Average</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={2 + Math.max(domainColumns.length, 1)}
                className="px-3 py-8 text-center text-gray-500"
              >
                No rows to display.
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.student_id ?? row.username} className="border-b border-gray-100 hover:bg-gray-50/80">
                <td className="sticky left-0 z-10 bg-white px-3 py-2 font-medium text-gray-900 shadow-[1px_0_0_#e5e7eb]">
                  {row.username}
                </td>
                {domainColumns.map((d) => {
                  const raw = row[d];
                  const isEmpty = raw == null || !Number.isFinite(Number(raw));
                  return (
                    <td
                      key={d}
                      className={`whitespace-nowrap px-3 py-2 text-center ${isEmpty ? 'bg-gray-50 text-gray-400' : scoreHeatmapCellClass(raw)}`}
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
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
