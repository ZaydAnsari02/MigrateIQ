"use client";

import { SummaryCard } from "@/components/ui/Card";
import { RunsTable } from "@/components/dashboard/RunsTable";
import type { DashboardStats, ValidationRun, ReportPair } from "@/types";
import { cn } from "@/lib/utils";

// ─── Mini pass-rate bar ───────────────────────────────────────────────────────

function PassRateBar({ rate }: { rate: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-zinc-100 rounded-full h-1.5 overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            rate >= 80 ? "bg-emerald-500" : rate >= 50 ? "bg-amber-400" : "bg-red-500"
          )}
          style={{ width: `${rate}%` }}
        />
      </div>
      <span className="text-xs font-bold text-zinc-600 w-8 text-right">{rate}%</span>
    </div>
  );
}

// ─── Activity row ─────────────────────────────────────────────────────────────

function ActivityRow({ pair }: { pair: ReportPair }) {
  const color = pair.overallStatus === "PASS" ? "text-emerald-500" :
                pair.overallStatus === "FAIL" ? "text-red-500" : "text-amber-400";
  const icon  = pair.overallStatus === "PASS" ? "✓" :
                pair.overallStatus === "FAIL" ? "✗" : "·";
  return (
    <div className="flex items-center gap-3 py-2 border-b border-zinc-50 last:border-0">
      <span className={cn("text-sm font-bold w-4 text-center shrink-0", color)}>{icon}</span>
      <span className="text-xs text-zinc-700 flex-1 truncate">{pair.reportName}</span>
      <div className="flex items-center gap-1">
        {([pair.layer1Status, pair.layer2Status, pair.layer3Status] as const).map((s, i) => (
          <span
            key={i}
            className={cn(
              "w-1.5 h-1.5 rounded-full",
              s === "pass" ? "bg-emerald-400" : s === "fail" ? "bg-red-400" : "bg-zinc-200"
            )}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Dashboard Overview ───────────────────────────────────────────────────────

interface DashboardOverviewProps {
  stats: DashboardStats;
  runs: ValidationRun[];
  pairs: ReportPair[];
}

export function DashboardOverview({ stats, runs, pairs }: DashboardOverviewProps) {
  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          label="Reports Checked"
          value={stats.totalReports}
          sub="This validation run"
          accent="blue"
        />
        <SummaryCard
          label="Passed"
          value={stats.passed}
          sub={`${stats.passRate}% pass rate`}
          accent="green"
        />
        <SummaryCard
          label="Failed"
          value={stats.failed}
          sub="Requires attention"
          accent="red"
        />
        <SummaryCard
          label="Pending"
          value={stats.pending}
          sub="Awaiting capture"
          accent="amber"
        />
      </div>

      {/* Pass rate + recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Pass rate card */}
        <div className="bg-white rounded-xl border border-zinc-200 shadow-card p-5">
          <h3 className="text-xs font-semibold text-zinc-700 mb-4">Overall Pass Rate</h3>
          <div className="flex items-end gap-2 mb-3">
            <span className="text-4xl font-bold text-zinc-900 tracking-tight">{stats.passRate}</span>
            <span className="text-lg font-bold text-zinc-400 mb-1">%</span>
          </div>
          <PassRateBar rate={stats.passRate} />
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            {[
              { label: "Passed",  value: stats.passed,  color: "text-emerald-600" },
              { label: "Failed",  value: stats.failed,  color: "text-red-600" },
              { label: "Pending", value: stats.pending, color: "text-amber-500" },
            ].map(s => (
              <div key={s.label} className="bg-zinc-50 rounded-lg p-2">
                <div className={cn("text-base font-bold", s.color)}>{s.value}</div>
                <div className="text-[9px] text-zinc-400 uppercase tracking-wide">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent activity */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-zinc-200 shadow-card p-5">
          <h3 className="text-xs font-semibold text-zinc-700 mb-3">Recent Report Results</h3>
          <div>
            {pairs.slice(0, 6).map(pair => (
              <ActivityRow key={pair.id} pair={pair} />
            ))}
          </div>
        </div>
      </div>

      {/* Runs history */}
      <RunsTable runs={runs} />
    </div>
  );
}
