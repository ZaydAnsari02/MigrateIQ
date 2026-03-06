"use client";

import { cn, formatDate, formatDuration } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/Card";
import { RunStatusChip } from "@/components/ui/Badge";
import type { ValidationRun } from "@/types";

interface RunsTableProps {
  runs: ValidationRun[];
  onSelect?: (run: ValidationRun) => void;
}

export function RunsTable({ runs, onSelect }: RunsTableProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-zinc-900">Validation Runs</h3>
          <p className="text-xs text-zinc-400 mt-0.5">History of all pipeline executions for this project</p>
        </div>
      </CardHeader>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-zinc-50 border-b border-zinc-100">
              {["Run ID", "Triggered By", "Reports", "Pass / Fail", "Duration", "Status", "Date"].map(col => (
                <th key={col} className="text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider px-5 py-3">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-50">
            {runs.map(run => (
              <tr
                key={run.id}
                onClick={() => onSelect?.(run)}
                className="hover:bg-zinc-50/60 cursor-pointer transition-colors"
              >
                <td className="px-5 py-3.5">
                  <span className="text-[10px] font-mono text-zinc-500 bg-zinc-50 border border-zinc-200 px-1.5 py-0.5 rounded">
                    {run.id}
                  </span>
                </td>
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-1.5">
                    <div className="w-5 h-5 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-[8px] font-bold">
                      {run.triggeredBy[0]}
                    </div>
                    <span className="text-xs text-zinc-700">{run.triggeredBy}</span>
                  </div>
                </td>
                <td className="px-5 py-3.5">
                  <span className="text-xs text-zinc-600">{run.totalReports}</span>
                </td>
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-emerald-600 font-semibold">{run.passed} ✓</span>
                    <span className="text-zinc-300">·</span>
                    <span className="text-red-500 font-semibold">{run.failed} ✗</span>
                  </div>
                </td>
                <td className="px-5 py-3.5">
                  <span className="text-[10px] font-mono text-zinc-500">
                    {run.completedAt ? formatDuration(run.startedAt, run.completedAt) : "—"}
                  </span>
                </td>
                <td className="px-5 py-3.5">
                  <RunStatusChip status={run.status} />
                </td>
                <td className="px-5 py-3.5">
                  <span className="text-[10px] text-zinc-400">{formatDate(run.startedAt)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
